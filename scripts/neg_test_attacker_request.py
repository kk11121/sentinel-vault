#!/usr/bin/env python3
"""Negative test: an attacker EOA (not the owner) calls
requestWithdrawal on the Base vault. Expected: the transaction is
broadcast and FAILS on-chain (NotOwner) — evidence that S1 is fixed."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web3 import Web3

from worker.worker import ENV, RPCS

w3 = Web3(Web3.HTTPProvider(RPCS[84532]))
attacker = w3.eth.account.from_key(ENV["ATTACKER_PRIVATE_KEY"])
vault = "0xAf17d1e294c35cA4eFE35c58B201D6F95Aef3DE4"
abi = [{
    "inputs": [{"name": "to_", "type": "address"}, {"name": "amount_", "type": "uint256"}],
    "name": "requestWithdrawal",
    "outputs": [{"name": "requestId", "type": "uint256"}],
    "stateMutability": "nonpayable",
    "type": "function",
}]
c = w3.eth.contract(address=vault, abi=abi)
tx = c.functions.requestWithdrawal(attacker.address, 1_000_000_000_000_000).build_transaction({
    "from": attacker.address,
    "nonce": w3.eth.get_transaction_count(attacker.address),
    "gas": 200_000,
    "maxFeePerGas": w3.eth.gas_price * 2,
    "maxPriorityFeePerGas": w3.eth.gas_price,
})
signed = attacker.sign_transaction(tx)
h = w3.eth.send_raw_transaction(signed.raw_transaction)
r = w3.eth.wait_for_transaction_receipt(h, timeout=180)
print(f"attacker requestWithdrawal tx: 0x{h.hex()} status: {r['status']} (0 = reverted as expected)")
