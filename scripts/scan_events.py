#!/usr/bin/env python3
"""Chunked event scan for evidence collection (Base RPC caps log ranges)."""
import sys

sys.path.insert(0, ".")
from web3 import Web3

from worker.worker import RPCS

VAULTS = {
    84532: "0xAf17d1e294c35cA4eFE35c58B201D6F95Aef3DE4",
    11155111: "0x0C0c54778431652a2c6b92E088fB02335d395BED",
    1301: "0x95Fd0764a2f75387F35c8eEAB409aa1410b19b2d",
}
RSC = "0xeaE20eccD1F308CaB3e8a4c99e588D8CC21a1ff8"


def scan(w3, address, from_block, to_block, chunk=49):
    out, start = [], from_block
    while start <= to_block:
        end = min(start + chunk, to_block)
        try:
            out += w3.eth.get_logs({"address": address, "fromBlock": start, "toBlock": end})
        except Exception as e:  # noqa: BLE001
            if "pruned" not in str(e):
                raise
        start = end + 1
    return out


def main():
    span = int(sys.argv[1]) if len(sys.argv) > 1 else 1500
    for cid, v in VAULTS.items():
        w3 = Web3(Web3.HTTPProvider(RPCS[cid]))
        head = w3.eth.block_number
        logs = scan(w3, v, head - span, head)
        print(f"== chain {cid} vault {v} head {head}")
        for l in logs:
            print("  block", l["blockNumber"], "tx", l["transactionHash"].hex(),
                  "topic0", l["topics"][0].hex()[:16], "ntopics", len(l["topics"]))
    w3 = Web3(Web3.HTTPProvider("https://lasna-rpc.rnk.dev"))
    head = w3.eth.block_number
    logs = scan(w3, RSC, head - span * 2, head)
    print("== Lasna RSC events")
    for l in logs:
        print("  block", l["blockNumber"], "tx", l["transactionHash"].hex(),
              "topic0", l["topics"][0].hex()[:16], "ntopics", len(l["topics"]))


if __name__ == "__main__":
    main()
