#!/usr/bin/env python3
"""Evidence-run driver for the v4/v5 stack. Usage: ev.py <cmd> [args]."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web3 import Web3
from eth_account import Account

from worker.worker import RPCS, ENV, VAULTS, REGISTRY, RSC

RPCS[5318007] = "https://lasna-rpc.rnk.dev"
DEPLOYER = Account.from_key(ENV["DEPLOYER_OWNER_PRIVATE_KEY"])
RECOVERY = Account.from_key(ENV["RECOVERY_PRIVATE_KEY"])
ATTACKER = Account.from_key(ENV["ATTACKER_PRIVATE_KEY"])

VAULT_ABI = json.loads("""[
 {"type":"function","name":"requestWithdrawal","inputs":[{"name":"to_","type":"address"},{"name":"amount_","type":"uint256"}],"outputs":[{"name":"requestId","type":"uint256"}],"stateMutability":"nonpayable"},
 {"type":"function","name":"executeWithdrawal","inputs":[{"name":"requestId_","type":"uint256"}],"outputs":[],"stateMutability":"nonpayable"},
 {"type":"function","name":"withdrawals","inputs":[{"name":"","type":"uint256"}],"outputs":[{"name":"requester","type":"address"},{"name":"to","type":"address"},{"name":"amount","type":"uint256"},{"name":"readyAt","type":"uint256"},{"name":"vetoed","type":"bool"},{"name":"executed","type":"bool"}],"stateMutability":"view"},
 {"type":"function","name":"nextRequestId","inputs":[],"outputs":[{"name":"","type":"uint256"}],"stateMutability":"view"},
 {"type":"function","name":"frozen","inputs":[],"outputs":[{"name":"","type":"bool"}],"stateMutability":"view"},
 {"type":"function","name":"pendingTotal","inputs":[],"outputs":[{"name":"","type":"uint256"}],"stateMutability":"view"},
 {"type":"function","name":"unfreeze","inputs":[],"outputs":[],"stateMutability":"nonpayable"},
 {"type":"function","name":"setWait","inputs":[{"name":"waitSeconds_","type":"uint256"}],"outputs":[],"stateMutability":"nonpayable"}
]""")
RSC_ABI = json.loads("""[
 {"type":"function","name":"paceCount","inputs":[],"outputs":[{"name":"","type":"uint256"}],"stateMutability":"view"},
 {"type":"function","name":"paceWindowStart","inputs":[],"outputs":[{"name":"","type":"uint256"}],"stateMutability":"view"},
 {"type":"function","name":"paceFrozen","inputs":[],"outputs":[{"name":"","type":"bool"}],"stateMutability":"view"}
]""")

EVENTS = {
    "RequestSeen": "RequestSeen(uint256,address,uint256)",
    "VetoRequested": "VetoRequested(uint256,address,uint256)",
    "FreezeRequested": "FreezeRequested(uint256,address,uint256)",
    "VerdictIgnored": "VerdictIgnored(uint256,uint8)",
    "UnverifiedVerdict": "UnverifiedVerdict(uint256,address,uint256,uint8)",
    "PendingVetoRecorded": "PendingVetoRecorded(uint256,address,uint256,uint8)",
    "PendingVetoApplied": "PendingVetoApplied(uint256,address,uint256,uint8)",
    "Escalated": "Escalated(uint256,address,uint256)",
    "PaceFreeze": "PaceFreeze(uint256,uint256)",
}


def w3of(cid):
    return Web3(Web3.HTTPProvider(RPCS[cid]))


def vault_of(cid):
    return w3of(cid).eth.contract(address=VAULTS[cid], abi=VAULT_ABI)


def send_as(w3, acct, fn, gas=1_200_000):
    tx = fn.build_transaction({
        "from": acct.address,
        "nonce": w3.eth.get_transaction_count(acct.address),
        "gas": gas,
        "maxFeePerGas": w3.eth.gas_price * 2,
        "maxPriorityFeePerGas": w3.eth.gas_price,
    })
    h = w3.eth.send_raw_transaction(acct.sign_transaction(tx).raw_transaction)
    r = w3.eth.wait_for_transaction_receipt(h, timeout=240)
    return h.hex(), r["status"], r["blockNumber"]


def main():
    cmd = sys.argv[1]
    if cmd == "req":
        cid, to, eth = int(sys.argv[2]), sys.argv[3], float(sys.argv[4])
        to = {"owner": DEPLOYER.address, "attacker": ATTACKER.address}.get(to, to)
        w3, v = w3of(cid), vault_of(cid)
        rid = v.functions.nextRequestId().call()
        h, st, blk = send_as(w3, DEPLOYER, v.functions.requestWithdrawal(to, Web3.to_wei(eth, "ether")))
        w = v.functions.withdrawals(rid).call()
        print(f"req chain={cid} id={rid} tx={h} status={st} block={blk} readyAt={w[3]}")
    elif cmd == "exec":
        cid, rid = int(sys.argv[2]), int(sys.argv[3])
        w3, v = w3of(cid), vault_of(cid)
        try:
            h, st, blk = send_as(w3, DEPLOYER, v.functions.executeWithdrawal(rid))
            print(f"exec chain={cid} id={rid} tx={h} status={st} block={blk}")
        except Exception as e:
            print(f"exec chain={cid} id={rid} FAILED to broadcast: {str(e)[:160]}")
    elif cmd == "raw":
        # raw <chain> <kind>: broadcast a tx expected to revert; print receipt status
        cid, kind = int(sys.argv[2]), sys.argv[3]
        w3, v = w3of(cid), vault_of(cid)
        if kind == "attacker_req":
            fn, acct = v.functions.requestWithdrawal(ATTACKER.address, Web3.to_wei(0.001, "ether")), ATTACKER
        elif kind == "owner_unfreeze":
            fn, acct = v.functions.unfreeze(), DEPLOYER
        elif kind == "zero_req":
            fn, acct = v.functions.requestWithdrawal(DEPLOYER.address, 0), DEPLOYER
        h, st, blk = send_as(w3, acct, fn)
        print(f"raw {kind} chain={cid} tx={h} status={st} block={blk}")
    elif cmd == "unfreeze":
        cid = int(sys.argv[2])
        w3, v = w3of(cid), vault_of(cid)
        h, st, blk = send_as(w3, RECOVERY, v.functions.unfreeze())
        print(f"unfreeze chain={cid} tx={h} status={st}")
    elif cmd == "setwait":
        cid, secs = int(sys.argv[2]), int(sys.argv[3])
        w3, v = w3of(cid), vault_of(cid)
        h, st, blk = send_as(w3, RECOVERY, v.functions.setWait(secs))
        print(f"setwait chain={cid} secs={secs} tx={h} status={st}")
    elif cmd == "vstate":
        cid, rid = int(sys.argv[2]), int(sys.argv[3])
        v = vault_of(cid)
        w = v.functions.withdrawals(rid).call()
        print(f"chain={cid} id={rid} to={w[1]} amount={w[2]/1e18} readyAt={w[3]} vetoed={w[4]} executed={w[5]}")
    elif cmd == "state":
        for cid in (84532, 11155111, 1301):
            v = vault_of(cid)
            print(f"chain={cid} frozen={v.functions.frozen().call()} pendingTotal={v.functions.pendingTotal().call()/1e18} nextId={v.functions.nextRequestId().call()}")
        lasna = w3of(5318007)
        rsc = lasna.eth.contract(address=RSC, abi=RSC_ABI)
        print(f"RSC paceCount={rsc.functions.paceCount().call()} paceFrozen={rsc.functions.paceFrozen().call()} windowStart={rsc.functions.paceWindowStart().call()} lasnaHead={lasna.eth.block_number}")
    elif cmd == "rsc_events":
        from_block = int(sys.argv[2])
        lasna = w3of(5318007)
        head = lasna.eth.block_number
        topics = {Web3.keccak(text=sig).hex(): name for name, sig in EVENTS.items()}
        logs = lasna.eth.get_logs({"address": RSC, "fromBlock": from_block, "toBlock": head})
        for lg in logs:
            t0 = lg["topics"][0].hex()
            name = topics.get(t0, t0[:12])
            print(f"block={lg['blockNumber']} tx={lg['transactionHash'].hex()} event={name}")
    elif cmd == "txtime":
        cid, txh = int(sys.argv[2]), sys.argv[3]
        w3 = w3of(cid)
        r = w3.eth.get_transaction_receipt(txh)
        b = w3.eth.get_block(r["blockNumber"])
        print(f"tx={txh} block={r['blockNumber']} ts={b['timestamp']} status={r['status']}")


if __name__ == "__main__":
    main()
