#!/usr/bin/env python3
"""Sentinel Vault worker — M3 model version.

Watches WithdrawalRequested events on all GuardedVaults, computes the
shared feature vector (model/features.py) from live chain state, scores
it with the exported Isolation Forest (model/model.json, pure-python
scorer — no pickle), and posts a verdict for EVERY request to the
VerdictRegistry on Base Sepolia using the verdictWriter key.

The worker can only judge; its key holds no power over funds. Verdicts
carry featuresHash + modelHash so anyone can replay them
(scripts/replay.py).

Delivery semantics: a verdict counts as delivered only when its
transaction receipt confirms success. The per-chain scan cursor never
advances past a request whose verdict is not yet posted; a failed
posting is retried on later poll cycles (head-of-line, so feature
order is preserved), and no single log's RPC failure can kill the
process.

Scanning is incremental: each poll cycle fetches and processes a
bounded slice of the backlog, advancing (and persisting) the cursor
chunk by chunk. The original loop fetched the whole cursor-to-head
range in one all-or-nothing pass, which after a restart meant ~1M
blocks on Base Sepolia — a single failed chunk discarded the entire
pass, so a restarted worker could never catch up. The persisted
cursor + history (worker/worker-state.json) make restarts resume
where the previous process stopped; a first start still rebuilds
everything from the deploy blocks.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web3 import Web3
from eth_account import Account

from model.features import PROFILES, compute_features, features_hash
from model.scorer import Model, model_hash

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_env():
    env = {}
    path = os.path.join(ROOT, ".env")
    if not os.path.exists(path):
        # Read-only use (e.g. scripts/replay.py from a clean clone) needs
        # no keys; only the live worker's verdict posting does.
        return env
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


ENV = load_env()
RPCS = {
    84532: "https://sepolia.base.org",
    11155111: "https://ethereum-sepolia-rpc.publicnode.com",
    1301: "https://sepolia.unichain.org",
}
# Addresses of the current deployment live in deployments.json at the
# repo root (written by the deploy step) so the worker, the replay tool
# and the README can never drift onto a stale stack. The literals below
# are the pre-review (v2) stack, used only if the file is missing.
REGISTRY = "0xEe60c9776CAc32bda21ED7e6cAD1497717B28A12"
VAULTS = {
    84532: "0xFf25f82b50c0164D815D0d18037afab502D2b926",
    11155111: "0x95Fd0764a2f75387F35c8eEAB409aa1410b19b2d",
    1301: "0x68A10a67C79593d6e4a69AB7Abc5762380Dc5560",
}
RSC = None


DEPLOY_BLOCKS = {}

# Scan state (cursor + rebuilt history) is persisted here after every
# processed chunk so a restart resumes where the previous process left
# off instead of rescanning from the deploy blocks. Runtime data only;
# gitignored, and ignored on load unless it matches the deployment in
# deployments.json.
STATE_PATH = os.path.join(ROOT, "worker", "worker-state.json")
# Upper bound on blocks fetched per chain per poll cycle while catching
# up; steady state is governed by the chain head, not this cap.
MAX_BLOCKS_PER_CYCLE = 40000
# eth_getLogs range per fetch, per chain (Base Sepolia's public RPC
# rejects ranges over 200 blocks; the others stay conservative).
CHUNK_SIZES = {84532: 200, 11155111: 50, 1301: 100}


def load_deployments():
    global REGISTRY, VAULTS, RSC, DEPLOY_BLOCKS
    path = os.path.join(ROOT, "deployments.json")
    if not os.path.exists(path):
        return
    import json

    with open(path) as f:
        d = json.load(f)
    REGISTRY = Web3.to_checksum_address(d["registry"])
    VAULTS = {int(cid): Web3.to_checksum_address(a) for cid, a in d["vaults"].items()}
    RSC = d.get("rsc")
    DEPLOY_BLOCKS = {int(cid): int(b) for cid, b in d.get("deployBlocks", {}).get("vaults", {}).items()}


def load_known_destinations():
    """Operator addresses for the first_seen feature: the committed list
    (worker/known_destinations.json) plus the vault addresses."""
    import json

    with open(os.path.join(ROOT, "worker", "known_destinations.json")) as f:
        entries = json.load(f)["addresses"]
    addrs = [Web3.to_checksum_address(e["address"]) for e in entries]
    addrs += [Web3.to_checksum_address(v) for v in VAULTS.values()]
    return addrs


load_deployments()
SEVERITY = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}

VAULT_ABI = [{
    "anonymous": False,
    "inputs": [
        {"indexed": True, "name": "requestId", "type": "uint256"},
        {"indexed": True, "name": "requester", "type": "address"},
        {"indexed": True, "name": "to", "type": "address"},
        {"indexed": False, "name": "amount", "type": "uint256"},
        {"indexed": False, "name": "readyAt", "type": "uint256"},
    ],
    "name": "WithdrawalRequested",
    "type": "event",
}]
REGISTRY_ABI = [
    {
        "inputs": [
            {"name": "chainId_", "type": "uint256"},
            {"name": "vault_", "type": "address"},
            {"name": "requestId_", "type": "uint256"},
            {"name": "severity_", "type": "uint8"},
            {"name": "score_", "type": "uint256"},
            {"name": "featuresHash_", "type": "bytes32"},
            {"name": "modelHash_", "type": "bytes32"},
        ],
        "name": "postVerdict",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "chainId_", "type": "uint256"},
            {"name": "vault_", "type": "address"},
            {"name": "requestId_", "type": "uint256"},
        ],
        "name": "hasVerdict",
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function",
    },
]


def main():
    writer = Account.from_key(ENV["VERDICT_WRITER_PRIVATE_KEY"])
    model = Model.load()
    mhash = model_hash()
    base = Web3(Web3.HTTPProvider(RPCS[84532]))
    registry = base.eth.contract(address=REGISTRY, abi=REGISTRY_ABI)
    connections = {cid: Web3(Web3.HTTPProvider(url)) for cid, url in RPCS.items()}
    vault_contracts = {
        cid: connections[cid].eth.contract(address=addr, abi=VAULT_ABI)
        for cid, addr in VAULTS.items()
    }
    # Runtime profile: the trained daily-small personality, with the
    # operator's own addresses as known destinations (committed list +
    # vault addresses — see worker/known_destinations.json).
    profile = dict(PROFILES["daily-small"])
    profile["known_destinations"] = load_known_destinations()
    # Start scanning at each vault's deployment block so the in-memory
    # history is rebuilt completely on restart (the 24h features need
    # all of it). Already-judged requests are appended to history and
    # then skipped via the registry's hasVerdict check.
    last_block = {
        cid: (DEPLOY_BLOCKS[cid] - 1 if cid in DEPLOY_BLOCKS
              else connections[cid].eth.block_number - 2000)
        for cid in RPCS
    }
    state = {"nonce": base.eth.get_transaction_count(writer.address)}
    history = {cid: [] for cid in RPCS}  # (timestamp, to, amount_eth)
    handled = set()
    # Verdict payloads are computed exactly once per request, from the
    # history of strictly earlier requests, in log order — the same
    # semantics scripts/replay.py reproduces. A request whose posting
    # fails keeps its prepared payload here and is retried on later
    # cycles; the scan cursor never advances past an unposted verdict,
    # so a transient RPC/gas failure delays a verdict but never drops
    # it (H1 fix from the second adversarial review, 2026-11-18; the
    # previous loop advanced the cursor at fetch time and lost the
    # verdict until the next process restart).
    prepared = {}

    # Resume the scan position and history from the state file when it
    # matches the current deployment; otherwise fall back to the full
    # rescan from the deploy blocks (the history is then rebuilt by the
    # same scan, just more slowly). The H1 delivery semantics above are
    # unchanged: the cursor still never advances past an unposted
    # verdict, it just advances chunk by chunk and survives restarts.
    resumed = False
    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH) as f:
                saved = json.load(f)
            saved_vaults = {int(k): v for k, v in saved["vaults"].items()}
            if saved.get("registry") == REGISTRY and saved_vaults == VAULTS:
                for cid in RPCS:
                    last_block[cid] = int(saved["last_block"][str(cid)])
                    history[cid] = [tuple(x) for x in saved["history"][str(cid)]]
                resumed = True
        except Exception:  # noqa: BLE001
            resumed = False

    def save_state():
        data = {
            "registry": REGISTRY,
            "vaults": VAULTS,
            "last_block": {str(cid): last_block[cid] for cid in RPCS},
            "history": {str(cid): history[cid] for cid in RPCS},
        }
        tmp = STATE_PATH + ".tmp"
        with open(tmp, "w") as f:
            json.dump(data, f)
        os.replace(tmp, STATE_PATH)

    def prepare(cid, log):
        """Compute the verdict payload for one log and record the
        request in history. Runs at most once per request."""
        w3 = connections[cid]
        a = log["args"]
        block = w3.eth.get_block(log["blockNumber"])
        amount_eth = a["amount"] / 1e18
        balance_eth = w3.eth.get_balance(
            VAULTS[cid], block_identifier=log["blockNumber"]
        ) / 1e18
        feats = compute_features(
            profile, history[cid], a["to"], amount_eth, block["timestamp"], balance_eth
        )
        level, s = model.severity(feats)
        fh = features_hash(feats, a["amount"], a["to"], feats[1] > 0.5)
        history[cid].append((block["timestamp"], a["to"], amount_eth))
        return level, s, fh, feats

    def process(cid, log):
        """Bring one request to a posted (or already-posted) verdict.

        Returns True when the request is fully dealt with and the scan
        cursor may advance past it; False to retry it on a later
        cycle. Every exception is contained here, so one bad log can
        neither kill the worker nor stall the other chains."""
        key = (cid, log["args"]["requestId"])
        if key in handled:
            return True
        try:
            if key not in prepared:
                prepared[key] = prepare(cid, log)
            level, s, fh, feats = prepared[key]
            a = log["args"]
            # The registry accepts exactly one verdict per request and
            # rejects duplicates on-chain; check first so re-scans and
            # retries stay no-ops once a verdict has landed (including
            # the case where a previous attempt's receipt wait timed
            # out but the transaction later succeeded).
            if registry.functions.hasVerdict(cid, VAULTS[cid], a["requestId"]).call():
                print(f"[worker] chain {cid} req {a['requestId']} already judged, skip", flush=True)
                handled.add(key)
                prepared.pop(key, None)
                return True
            tx = registry.functions.postVerdict(
                cid, VAULTS[cid], a["requestId"], SEVERITY[level], s, fh, mhash
            ).build_transaction({
                "from": writer.address,
                "nonce": state["nonce"],
                "gas": 200_000,
                "maxFeePerGas": base.eth.gas_price * 2,
                "maxPriorityFeePerGas": base.eth.gas_price,
            })
            signed = writer.sign_transaction(tx)
            h = base.eth.send_raw_transaction(signed.raw_transaction)
            state["nonce"] += 1
            receipt = base.eth.wait_for_transaction_receipt(h, timeout=180)
            if receipt["status"] != 1:
                raise RuntimeError(f"verdict tx {h.hex()} reverted")
            print(
                f"[worker] chain {cid} req {a['requestId']} to={a['to']} "
                f"amount={a['amount']} feats={[round(f, 2) for f in feats]} "
                f"-> {level} ({s}) verdict tx {h.hex()}",
                flush=True,
            )
            handled.add(key)
            prepared.pop(key, None)
            return True
        except Exception as e:  # noqa: BLE001
            state["nonce"] = base.eth.get_transaction_count(writer.address)
            print(f"[worker] chain {cid} req {log['args']['requestId']} not posted, will retry: {e}", flush=True)
            return False

    print(
        f"[worker] {model.data.get('version', 'iforest')} up; writer={writer.address} "
        f"registry={REGISTRY} modelHash=0x{mhash.hex()} thresholds={model.thresholds}",
        flush=True,
    )
    print(
        f"[worker] scan state: "
        f"{'resumed from worker-state.json' if resumed else 'fresh rescan from deploy blocks'}",
        flush=True,
    )
    while True:
        try:
            for cid, vault in vault_contracts.items():
                w3 = connections[cid]
                try:
                    head = w3.eth.block_number - 2  # margin against RPC head skew
                except Exception as e:  # noqa: BLE001
                    print(f"[worker] poll error chain {cid}: {e}", flush=True)
                    continue
                # Fetch and process in bounded slices, advancing the
                # cursor chunk by chunk (and persisting it) instead of
                # one all-or-nothing pass from the cursor to the head:
                # after a restart the backlog is ~1M blocks on Base, and
                # a single failed chunk used to discard the whole pass,
                # so a restarted worker could never catch up.
                budget_end = min(head, last_block[cid] + MAX_BLOCKS_PER_CYCLE)
                while last_block[cid] < budget_end:
                    start = last_block[cid] + 1
                    end = min(start + CHUNK_SIZES.get(cid, 50) - 1, budget_end)
                    try:
                        logs = vault.events.WithdrawalRequested().get_logs(
                            from_block=start, to_block=end
                        )
                    except Exception as e:  # noqa: BLE001
                        print(f"[worker] poll error chain {cid}: {e}", flush=True)
                        break
                    blocked = False
                    for log in logs:
                        if process(cid, log):
                            last_block[cid] = max(last_block[cid], log["blockNumber"])
                        else:
                            # Head-of-line block: keep the cursor before
                            # this log's block so the request is re-fetched
                            # and retried next cycle. Later requests on
                            # this chain wait behind it, preserving the
                            # feature order replay reproduces; other
                            # chains proceed.
                            last_block[cid] = min(last_block[cid], log["blockNumber"] - 1)
                            blocked = True
                            break
                    if not blocked:
                        last_block[cid] = max(last_block[cid], end)
                    save_state()
                    if blocked:
                        break
        except Exception as e:  # noqa: BLE001
            print(f"[worker] cycle error, continuing: {e}", flush=True)
        time.sleep(10)


if __name__ == "__main__":
    sys.exit(main())
