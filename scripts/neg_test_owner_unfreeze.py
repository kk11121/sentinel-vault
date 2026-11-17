#!/usr/bin/env python3
"""Negative test: the OWNER (daily key) calls unfreeze() on a frozen
vault. Expected: broadcast and FAIL on-chain (NotRecovery) — only the
recovery key can unfreeze (S3 fix)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web3 import Web3

from worker.worker import ENV, RPCS

w3 = Web3(Web3.HTTPProvider(RPCS[84532]))
owner = w3.eth.account.from_key(ENV["DEPLOYER_OWNER_PRIVATE_KEY"])
vault = "0xAf17d1e294c35cA4eFE35c58B201D6F95Aef3DE4"
abi = [{"inputs": [], "name": "unfreeze", "outputs": [], "stateMutability": "nonpayable", "type": "function"}]
c = w3.eth.contract(address=vault, abi=abi)
tx = c.functions.unfreeze().build_transaction({
    "from": owner.address,
    "nonce": w3.eth.get_transaction_count(owner.address),
    "gas": 120_000,
    "maxFeePerGas": w3.eth.gas_price * 2,
    "maxPriorityFeePerGas": w3.eth.gas_price,
})
signed = owner.sign_transaction(tx)
h = w3.eth.send_raw_transaction(signed.raw_transaction)
r = w3.eth.wait_for_transaction_receipt(h, timeout=180)
print(f"owner unfreeze tx: 0x{h.hex()} status: {r['status']} (0 = reverted as expected)")
