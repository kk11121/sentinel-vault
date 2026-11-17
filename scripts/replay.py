#!/usr/bin/env python3
"""Replay a verdict after the fact.

Given a vault chain, vault address and requestId, this tool:
  1. finds the WithdrawalRequested event and the VerdictPosted event,
  2. rebuilds the vault's withdrawal history from chain events,
  3. recomputes features + score + severity with the shipped model,
  4. compares everything against the on-chain verdict.

Exit code 0 iff every field matches. This is the audit path the design
promises: "auditable after the fact".

Usage: .venv/bin/python scripts/replay.py --chain 11155111 --request-id 1
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web3 import Web3

from model.features import PROFILES, compute_features, features_hash
from model.scorer import Model, model_hash
from worker.worker import ENV, REGISTRY, RPCS, VAULTS, VAULT_ABI

VERDICT_ABI = [{
    "anonymous": False,
    "inputs": [
        {"indexed": True, "name": "requestId", "type": "uint256"},
        {"indexed": True, "name": "vault", "type": "address"},
        {"indexed": False, "name": "severity", "type": "uint8"},
        {"indexed": False, "name": "score", "type": "uint256"},
        {"indexed": False, "name": "featuresHash", "type": "bytes32"},
        {"indexed": False, "name": "modelHash", "type": "bytes32"},
    ],
    "name": "VerdictPosted",
    "type": "event",
}]
SEV = {0: "LOW", 1: "MEDIUM", 2: "HIGH"}


def scan(event, from_block, to_block, chunk=49):
    out, start = [], from_block
    while start <= to_block:
        end = min(start + chunk, to_block)
        try:
            out += event.get_logs(from_block=start, to_block=end)
        except Exception as e:  # noqa: BLE001
            if "pruned" not in str(e):
                raise
            print(f"  (skipping pruned range {start}-{end})")
        start = end + 1
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chain", type=int, required=True)
    ap.add_argument("--request-id", type=int, required=True)
    ap.add_argument("--lookback", type=int, default=4000)
    args = ap.parse_args()

    cid = args.chain
    vault_addr = VAULTS[cid]
    w3 = Web3(Web3.HTTPProvider(RPCS[cid]))
    base = Web3(Web3.HTTPProvider(RPCS[84532]))
    vault = w3.eth.contract(address=vault_addr, abi=VAULT_ABI)
    registry = base.eth.contract(address=REGISTRY, abi=VERDICT_ABI)

    head = w3.eth.block_number
    reqs = scan(vault.events.WithdrawalRequested(), head - args.lookback, head)
    target = next((l for l in reqs if l["args"]["requestId"] == args.request_id), None)
    if target is None:
        print(f"request {args.request_id} not found on chain {cid} in lookback window")
        return 1
    bhead = base.eth.block_number
    verdicts = scan(registry.events.VerdictPosted(), bhead - 20000, bhead)
    verdict = next(
        (l for l in verdicts
         if l["args"]["requestId"] == args.request_id
         and l["args"]["vault"] == vault_addr),
        None,
    )
    if verdict is None:
        print("no verdict found for this request")
        return 1

    profile = dict(PROFILES["daily-small"])
    profile["known_destinations"] = [
        Web3.to_checksum_address(ENV["DEPLOYER_OWNER_ADDRESS"]),
        Web3.to_checksum_address(ENV["VERDICT_WRITER_ADDRESS"]),
        *[Web3.to_checksum_address(v) for v in VAULTS.values()],
    ]
    history = []
    for l in reqs:
        if l["blockNumber"] >= target["blockNumber"]:
            break
        b = w3.eth.get_block(l["blockNumber"])
        history.append((b["timestamp"], l["args"]["to"], l["args"]["amount"] / 1e18))

    a = target["args"]
    block = w3.eth.get_block(target["blockNumber"])
    balance_eth = w3.eth.get_balance(vault_addr, block_identifier=target["blockNumber"]) / 1e18
    feats = compute_features(profile, history, a["to"], a["amount"] / 1e18, block["timestamp"], balance_eth)
    model = Model.load()
    level, s = model.severity(feats)
    fh = features_hash(feats, a["amount"], a["to"], feats[1] > 0.5)

    va = verdict["args"]
    checks = [
        ("severity", level, SEV[va["severity"]]),
        ("score", s, va["score"]),
        ("featuresHash", "0x" + fh.hex(), "0x" + va["featuresHash"].hex()),
        ("modelHash", "0x" + model_hash().hex(), "0x" + va["modelHash"].hex()),
    ]
    print(f"replay chain {cid} vault {vault_addr} request {args.request_id}")
    print(f"features: {[round(f, 4) for f in feats]}")
    ok = True
    for name, mine, chain_val in checks:
        match = mine == chain_val
        ok &= match
        print(f"  {name}: replay={mine} onchain={chain_val} {'MATCH' if match else 'MISMATCH'}")
    print("RESULT:", "MATCH" if ok else "MISMATCH")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
