#!/usr/bin/env python3
"""Sentinel Vault worker — M2 dummy-rule version.

Watches WithdrawalRequested events on all GuardedVaults, scores each
request with a fixed rule (M3 replaces this with the real model), and
posts a verdict for EVERY request to the VerdictRegistry on Base Sepolia
using the verdictWriter key. The worker can only judge; it holds no power
over funds.

Rule v1:
  - destination is a known address (owner/keys/vaults) -> LOW
  - amount >= HIGH_AMOUNT                              -> HIGH
  - first-seen destination                             -> MEDIUM
  - otherwise                                          -> LOW
"""
import os
import sys
import time

from web3 import Web3
from eth_account import Account

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_env():
    env = {}
    with open(os.path.join(ROOT, ".env")) as f:
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
REGISTRY = "0xEe60c9776CAc32bda21ED7e6cAD1497717B28A12"
VAULTS = {
    84532: "0xFf25f82b50c0164D815D0d18037afab502D2b926",
    11155111: "0x95Fd0764a2f75387F35c8eEAB409aa1410b19b2d",
    1301: "0x68A10a67C79593d6e4a69AB7Abc5762380Dc5560",
}
KNOWN = {
    Web3.to_checksum_address(ENV["DEPLOYER_OWNER_ADDRESS"]),
    Web3.to_checksum_address(ENV["VERDICT_WRITER_ADDRESS"]),
} | {Web3.to_checksum_address(v) for v in VAULTS.values()}
HIGH_AMOUNT = Web3.to_wei(0.008, "ether")
MODEL_HASH = Web3.keccak(text="rule-worker-v1")
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
REGISTRY_ABI = [{
    "inputs": [
        {"name": "requestId_", "type": "uint256"},
        {"name": "vault_", "type": "address"},
        {"name": "severity_", "type": "uint8"},
        {"name": "score_", "type": "uint256"},
        {"name": "featuresHash_", "type": "bytes32"},
        {"name": "modelHash_", "type": "bytes32"},
    ],
    "name": "postVerdict",
    "outputs": [],
    "stateMutability": "nonpayable",
    "type": "function",
}]


def score(chain_id, vault, request_id, to, amount, seen_destinations):
    first_seen = to not in seen_destinations and to not in KNOWN
    if to in KNOWN:
        level, s = "LOW", 100
    elif amount >= HIGH_AMOUNT:
        level, s = "HIGH", 900
    elif first_seen:
        level, s = "MEDIUM", 600
    else:
        level, s = "LOW", 100
    features_hash = Web3.keccak(
        amount.to_bytes(32, "big")
        + bytes.fromhex(to[2:].rjust(40, "0"))
        + (b"\x01" if first_seen else b"\x00")
    )
    return level, s, features_hash, first_seen


def main():
    writer = Account.from_key(ENV["VERDICT_WRITER_PRIVATE_KEY"])
    base = Web3(Web3.HTTPProvider(RPCS[84532]))
    registry = base.eth.contract(address=REGISTRY, abi=REGISTRY_ABI)
    connections = {cid: Web3(Web3.HTTPProvider(url)) for cid, url in RPCS.items()}
    vault_contracts = {
        cid: connections[cid].eth.contract(address=addr, abi=VAULT_ABI)
        for cid, addr in VAULTS.items()
    }
    last_block = {cid: connections[cid].eth.block_number - 2000 for cid in RPCS}
    state = {"nonce": base.eth.get_transaction_count(writer.address)}
    seen_destinations = set()
    handled = set()
    print(f"[worker] rule-v1 up; writer={writer.address}", flush=True)
    while True:
        for cid, vault in vault_contracts.items():
            w3 = connections[cid]
            try:
                head = w3.eth.block_number
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
                level, s, fh, first_seen = score(
                    cid, VAULTS[cid], a["requestId"], a["to"], a["amount"], seen_destinations
                )
                seen_destinations.add(a["to"])
                try:
                    tx = registry.functions.postVerdict(
                        a["requestId"], VAULTS[cid], SEVERITY[level], s, fh, MODEL_HASH
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
                        f"amount={a['amount']} first_seen={first_seen} -> {level} ({s}) "
                        f"verdict tx {h.hex()}",
                        flush=True,
                    )
                except Exception as e:  # noqa: BLE001
                    state["nonce"] = base.eth.get_transaction_count(writer.address)
                    handled.discard(key)
                    print(f"[worker] post failed for {key}, will retry: {e}", flush=True)
        time.sleep(10)


if __name__ == "__main__":
    sys.exit(main())
