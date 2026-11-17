#!/usr/bin/env python3
"""Print block timestamps for a list of (chain, tx) pairs — latency evidence."""
import sys

sys.path.insert(0, ".")
from web3 import Web3

from worker.worker import RPCS

RPCS[5318007] = "https://lasna-rpc.rnk.dev"

PAIRS = [
    ("A request (Base)", 84532, "0xeebd5b7e694dd1ecf234a31c69800cb4e6168a57264225fa39c24b77774978da"),
    ("A verdict LOW (Base)", 84532, "0xd9566a099b529eb0a4a781b161d9ca82a5e9536f56d18f97a623fc1a6d6d17b8"),
    ("A RequestSeen (Lasna)", 5318007, "0x4dfa549d1f658a2bd554ceb2e757b74dbefda8fa7b53cad379e2200fb942a3b7"),
    ("A executed (Base)", 84532, "0x15edb14cc5393733e86372b61cde3f8c87d7d7650fac692040fe17576e2cb6be"),
    ("E req2 verdict MEDIUM (Base)", 84532, "0xc928d167388426fc77f437a4cd60fcaecfb54df74147984021b820d717d2e88a"),
    ("E req2 veto callback (Base)", 84532, "0xa5c2bc1c8c291860a9d7afe6e25714106d1bb81a086f225f12cbf7a4da4897a3"),
    ("E req3 verdict HIGH (Base)", 84532, "0xa0ee51c8d547a8d1630b7a2108005d9c2595d4b48070e2d99192126bc9f559bc"),
    ("E req3 freeze cb (Base)", 84532, "0xce4bd4742251bebd2e616c6a846abb6416d419d4af3f6b350f8a5b7d4bf2acb4"),
    ("E req3 freeze cb (Sepolia)", 11155111, "0x68a8b1b2f129eae8ace86a9eaaeb93b322394e74298a8365745a595fca9ba090"),
    ("E req3 freeze cb (Unichain)", 1301, "0x1f3600be20a360e8792d6775b78ffb9baac9ad56a6bf5b89076928c2e3d28d35"),
    ("Sep req2 verdict MEDIUM (Base)", 84532, "0x72f21003e798f377ec6ded77d2afd09f45a4ebca59fab9f89f0ed2f565d066e0"),
    ("Pace 11th request (Base)", 84532, "0x0af58b70933a5ac581a27c69aa8f709ecb6aaad234095a6a7545b6a9a47aa2f1"),
    ("Pace reactive tx (Lasna)", 5318007, "0xf5aeb1e9e1603adbc90b695e10241d1e540a25692cea8ebe0283621b0eaf0fbc"),
    ("Pace freeze cb (Base)", 84532, "0x98bfb7b81bc7d90c776fd8cd21a9b5b9de1fc6524ea542765db67e69126814d7"),
    ("Pace freeze cb (Sepolia)", 11155111, "0xcce2cf3e2ccb90333d8c01a0d1ed007b86c5f5ebc9506709e8d5102c6721ab84"),
    ("Pace freeze cb (Unichain)", 1301, "0xd6b22bc1d072217978c99d7e615b0fc69708966c10bcdb483d5c93ef2dff82ac"),
]

for label, cid, txh in PAIRS:
    w3 = Web3(Web3.HTTPProvider(RPCS[cid]))
    r = w3.eth.get_transaction_receipt(txh)
    b = w3.eth.get_block(r["blockNumber"])
    print(f"{label}: block {r['blockNumber']} ts {b['timestamp']} status {r['status']}")
