#!/usr/bin/env python3
"""Print the LIVE configuration of the deployed stack as a markdown
table, read from chain — so the README's numbers can never drift from
the deployments again (the pre-review README quoted a threshold the
owner had already changed). Run before submission and paste the output
into README.md's Configuration section.

Usage: .venv/bin/python scripts/print_config.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web3 import Web3

from worker.worker import RPCS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VAULT_ABI = [
    {"inputs": [], "name": n, "outputs": [{"name": "", "type": t}], "stateMutability": "view", "type": "function"}
    for n, t in [
        ("owner", "address"), ("recovery", "address"), ("frozen", "bool"),
        ("waitSeconds", "uint256"), ("largeThreshold", "uint256"),
        ("instantCap", "uint256"), ("instantWindowSeconds", "uint256"),
    ]
]
CHAIN_NAMES = {84532: "Base Sepolia", 11155111: "Ethereum Sepolia", 1301: "Unichain Sepolia"}


def main():
    with open(os.path.join(ROOT, "deployments.json")) as f:
        d = json.load(f)
    print("| chain | vault | balance | waitSeconds | largeThreshold | instantCap / window | frozen |")
    print("|---|---|---|---|---|---|---|")
    for cid_s, addr in sorted(d["vaults"].items(), key=lambda kv: int(kv[0])):
        cid = int(cid_s)
        w3 = Web3(Web3.HTTPProvider(RPCS[cid]))
        v = w3.eth.contract(address=addr, abi=VAULT_ABI)
        bal = w3.eth.get_balance(addr) / 1e18
        print(
            f"| {CHAIN_NAMES.get(cid, cid)} | `{addr}` | {bal:.4f} ETH "
            f"| {v.functions.waitSeconds().call()} s "
            f"| {v.functions.largeThreshold().call() / 1e18:.4f} ETH "
            f"| {v.functions.instantCap().call() / 1e18:.4f} ETH / {v.functions.instantWindowSeconds().call()} s "
            f"| {v.functions.frozen().call()} |"
        )
    lasna = Web3(Web3.HTTPProvider("https://lasna-rpc.rnk.dev"))
    rsc = d["rsc"]
    sys_contract = lasna.eth.contract(
        address="0x8888888888888888888888888888888888888888",
        abi=[{"inputs": [{"name": "", "type": "address"}], "name": "reserves",
              "outputs": [{"name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"}],
    )
    print()
    print(f"RSC `{rsc}` (Lasna): balance {lasna.eth.get_balance(rsc) / 1e18:.4f} lREACT, "
          f"reserves {sys_contract.functions.reserves(rsc).call() / 1e18:.4f} lREACT")
    print(f"VerdictRegistry (Base Sepolia): `{d['registry']}`")


if __name__ == "__main__":
    main()
