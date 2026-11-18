#!/usr/bin/env python3
"""Deploy the v6 stack: SentinelReactive v6 + GuardedVault v5 x3.

Changes vs v5/v4 (2026-11-18 second review, funded by the owner's own
faucet session): RSC checks verdicts against the watched table (M1) and
counts each withdrawal log once (M6); the vault gains cancelWithdrawal.
The registry is unchanged. The old stack is drained separately, after
the new evidence run completes.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web3 import Web3
from eth_account import Account

from worker.worker import RPCS, ENV

RPCS[5318007] = "https://lasna-rpc.rnk.dev"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEPLOYER = Account.from_key(ENV["DEPLOYER_OWNER_PRIVATE_KEY"])
RECOVERY_ADDR = ENV["RECOVERY_ADDRESS"]
REGISTRY = "0x0e55C8F84F44336b766Af8469b74d5163abB7F32"
PROXIES = {
    84532: "0x476F44b11F5C942c58f4c8E3d0300E5710743585",
    11155111: "0xAa14d9Cd0f788Ca23d11805986C1d8bd035D23b4",
    1301: "0x775c9B990ADe401060B78D0e98684eEf8d2466C1",
}
FUND = {84532: 0.012, 11155111: 0.012, 1301: 0.0008}


def w3of(cid):
    return Web3(Web3.HTTPProvider(RPCS[cid]))


def send(w3, fn, value=0):
    try:
        gas = int(fn.estimate_gas({"from": DEPLOYER.address, "value": value}) * 1.3)
    except Exception:
        gas = 600_000
    tx = fn.build_transaction({
        "from": DEPLOYER.address,
        "nonce": w3.eth.get_transaction_count(DEPLOYER.address),
        "gas": gas,
        "value": value,
        "maxFeePerGas": w3.eth.gas_price * 2,
        "maxPriorityFeePerGas": w3.eth.gas_price,
    })
    signed = DEPLOYER.sign_transaction(tx)
    h = w3.eth.send_raw_transaction(signed.raw_transaction)
    r = w3.eth.wait_for_transaction_receipt(h, timeout=240)
    return h.hex(), r


def load_bytecode(name):
    with open(os.path.join(ROOT, "out", f"{name}.sol", f"{name}.json")) as f:
        return json.load(f)["bytecode"]["object"]


def deploy_contract(w3, bytecode, abi, args, value=0):
    c = w3.eth.contract(abi=abi, bytecode=bytecode)
    est = c.constructor(*args).estimate_gas({"from": DEPLOYER.address, "value": value})
    tx = c.constructor(*args).build_transaction({
        "from": DEPLOYER.address,
        "nonce": w3.eth.get_transaction_count(DEPLOYER.address),
        "gas": int(est * 1.2),
        "value": value,
        "maxFeePerGas": w3.eth.gas_price * 2,
        "maxPriorityFeePerGas": w3.eth.gas_price,
    })
    signed = DEPLOYER.sign_transaction(tx)
    h = w3.eth.send_raw_transaction(signed.raw_transaction)
    r = w3.eth.wait_for_transaction_receipt(h, timeout=240)
    return r["contractAddress"], h.hex(), r


RSC_ABI = json.loads("""
[
 {"type":"constructor","inputs":[{"name":"registry_","type":"address"}],"stateMutability":"payable"},
 {"type":"function","name":"watchVault","inputs":[{"name":"chainId_","type":"uint256"},{"name":"vault_","type":"address"}],"outputs":[],"stateMutability":"nonpayable"}
]
""")
VAULT_CTOR_ABI = json.loads("""
[
 {"type":"constructor","inputs":[{"name":"owner_","type":"address"},{"name":"recovery_","type":"address"},{"name":"callbackProxy_","type":"address"},{"name":"callbackSender_","type":"address"},{"name":"waitSeconds_","type":"uint256"},{"name":"largeThreshold_","type":"uint256"},{"name":"instantCap_","type":"uint256"},{"name":"instantWindowSeconds_","type":"uint256"}],"stateMutability":"payable"}
]
""")
SYS_ABI = json.loads("""
[
 {"type":"function","name":"depositTo","inputs":[{"name":"addr","type":"address"}],"outputs":[],"stateMutability":"payable"},
 {"type":"function","name":"reserves","inputs":[{"name":"addr","type":"address"}],"outputs":[{"name":"","type":"uint256"}],"stateMutability":"view"}
]
""")


def main():
    lasna = w3of(5318007)
    print(f"deployer Lasna balance: {lasna.eth.get_balance(DEPLOYER.address)/1e18:.4f}")
    rsc_addr, rsc_tx, rsc_rcpt = deploy_contract(
        lasna, load_bytecode("SentinelReactive"), RSC_ABI, [REGISTRY],
        value=Web3.to_wei(0.8, "ether"),
    )
    print(f"RSC v6: {rsc_addr} tx={rsc_tx} block={rsc_rcpt['blockNumber']} status={rsc_rcpt['status']}")
    sys_c = lasna.eth.contract(address="0x8888888888888888888888888888888888888888", abi=SYS_ABI)
    h, r = send(lasna, sys_c.functions.depositTo(rsc_addr), value=Web3.to_wei(1.0, "ether"))
    print(f"depositTo reserves tx={h} status={r['status']} reserves={sys_c.functions.reserves(rsc_addr).call()/1e18}")

    vaults, blocks = {}, {"registry": 60039272, "rsc": rsc_rcpt["blockNumber"], "vaults": {}}
    rsc = lasna.eth.contract(address=rsc_addr, abi=RSC_ABI)
    for cid in (84532, 11155111, 1301):
        w3 = w3of(cid)
        addr, txh, rcpt = deploy_contract(
            w3, load_bytecode("GuardedVault"), VAULT_CTOR_ABI,
            [DEPLOYER.address, RECOVERY_ADDR, PROXIES[cid], rsc_addr,
             180, Web3.to_wei(0.004, "ether"), Web3.to_wei(0.008, "ether"), 3600],
            value=Web3.to_wei(FUND[cid], "ether"),
        )
        print(f"Vault v5 chain {cid}: {addr} tx={txh} block={rcpt['blockNumber']} status={rcpt['status']} funded={FUND[cid]}")
        vaults[str(cid)] = addr
        blocks["vaults"][str(cid)] = rcpt["blockNumber"]
        h, r = send(lasna, rsc.functions.watchVault(cid, addr))
        print(f"  watchVault tx={h} status={r['status']}")

    out = {
        "stack": "v5/v6 (second review: M1, M6, cancel)",
        "registry": REGISTRY,
        "rsc": rsc_addr,
        "vaults": vaults,
        "deployBlocks": blocks,
    }
    with open(os.path.join(ROOT, "deployments.json.new"), "w") as f:
        json.dump(out, f, indent=2)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
