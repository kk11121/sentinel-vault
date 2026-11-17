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
"""
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


def load_deployments():
    global REGISTRY, VAULTS, RSC
    path = os.path.join(ROOT, "deployments.json")
    if not os.path.exists(path):
        return
    import json

    with open(path) as f:
        d = json.load(f)
    REGISTRY = Web3.to_checksum_address(d["registry"])
    VAULTS = {int(cid): Web3.to_checksum_address(a) for cid, a in d["vaults"].items()}
    RSC = d.get("rsc")


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
    last_block = {cid: connections[cid].eth.block_number - 2000 for cid in RPCS}
    state = {"nonce": base.eth.get_transaction_count(writer.address)}
    history = {cid: [] for cid in RPCS}  # (timestamp, to, amount_eth)
    handled = set()
    print(
        f"[worker] {model.data.get('version', 'iforest')} up; writer={writer.address} "
        f"registry={REGISTRY} modelHash=0x{mhash.hex()} thresholds={model.thresholds}",
        flush=True,
    )
    while True:
        for cid, vault in vault_contracts.items():
            w3 = connections[cid]
            try:
                head = w3.eth.block_number - 2  # margin against RPC head skew
                if head <= last_block[cid]:
                    continue
                logs = []
                start = last_block[cid] + 1
                while start <= head:
                    end = min(start + 49, head)
                    logs += vault.events.WithdrawalRequested().get_logs(
                        from_block=start, to_block=end
                    )
                    start = end + 1
                last_block[cid] = head
            except Exception as e:  # noqa: BLE001
                print(f"[worker] poll error chain {cid}: {e}", flush=True)
                continue
            for log in logs:
                key = (cid, log["args"]["requestId"])
                if key in handled:
                    continue
                handled.add(key)
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
                # The registry accepts exactly one verdict per request and
                # rejects duplicates on-chain; check first so a restarted
                # worker re-scanning old blocks stays a no-op.
                try:
                    if registry.functions.hasVerdict(cid, VAULTS[cid], a["requestId"]).call():
                        print(f"[worker] chain {cid} req {a['requestId']} already judged, skip", flush=True)
                        continue
                except Exception as e:  # noqa: BLE001
                    print(f"[worker] hasVerdict check failed for {key}: {e}", flush=True)
                try:
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
                    print(
                        f"[worker] chain {cid} req {a['requestId']} to={a['to']} "
                        f"amount={a['amount']} feats={[round(f, 2) for f in feats]} "
                        f"-> {level} ({s}) verdict tx {h.hex()}",
                        flush=True,
                    )
                except Exception as e:  # noqa: BLE001
                    state["nonce"] = base.eth.get_transaction_count(writer.address)
                    handled.discard(key)
                    print(f"[worker] post failed for {key}, will retry: {e}", flush=True)
        time.sleep(10)


if __name__ == "__main__":
    sys.exit(main())
