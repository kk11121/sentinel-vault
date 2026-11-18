#!/usr/bin/env python3
"""Redeploy after the 2026-11-18 audit: SentinelReactive v5 + GuardedVault v4.

Stages (run in order):
  drain   — request the old vaults' balances back to the deployer
  drainx  — execute those requests after the 180 s wait
  deploy  — deploy RSC v5 (Lasna) + GuardedVault v4 x3, watchVault x3,
            fund everything, write deployments.json.new
"""
import json
import os
import sys
import time

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
FUND = {84532: 0.02, 11155111: 0.008, 1301: 0.012}

VAULT_ABI = json.loads("""[
 {"type":"function","name":"requestWithdrawal","inputs":[{"name":"to_","type":"address"},{"name":"amount_","type":"uint256"}],"outputs":[{"name":"requestId","type":"uint256"}],"stateMutability":"nonpayable"},
 {"type":"function","name":"executeWithdrawal","inputs":[{"name":"requestId_","type":"uint256"}],"outputs":[],"stateMutability":"nonpayable"},
 {"type":"function","name":"withdrawals","inputs":[{"name":"","type":"uint256"}],"outputs":[{"name":"requester","type":"address"},{"name":"to","type":"address"},{"name":"amount","type":"uint256"},{"name":"readyAt","type":"uint256"},{"name":"vetoed","type":"bool"},{"name":"executed","type":"bool"}],"stateMutability":"view"},
 {"type":"function","name":"nextRequestId","inputs":[],"outputs":[{"name":"","type":"uint256"}],"stateMutability":"view"}
]""")


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
    r = w3.eth.wait_for_transaction_receipt(h, timeout=180)
    return h.hex(), r


def old_deployments():
    with open(os.path.join(ROOT, "deployments.json")) as f:
        return json.load(f)


def stage_drain():
    d = old_deployments()
    for cid, addr in d["vaults"].items():
        cid = int(cid)
        w3 = w3of(cid)
        vault = w3.eth.contract(address=addr, abi=VAULT_ABI)
        bal = w3.eth.get_balance(addr)
        amount = bal - Web3.to_wei(0.0002, "ether")
        rid = vault.functions.nextRequestId().call()
        h, r = send(w3, vault.functions.requestWithdrawal(DEPLOYER.address, amount))
        print(f"chain {cid} old vault {addr}: drain request id={rid} amount={amount/1e18} tx={h} status={r['status']}")


def stage_drainx():
    d = old_deployments()
    for cid, addr in d["vaults"].items():
        cid = int(cid)
        w3 = w3of(cid)
        vault = w3.eth.contract(address=addr, abi=VAULT_ABI)
        # the drain request is the last one issued on each old vault
        rid = vault.functions.nextRequestId().call() - 1
        w = vault.functions.withdrawals(rid).call()
        now = w3.eth.get_block("latest")["timestamp"]
        if now < w[3]:
            print(f"chain {cid}: not ready, {w[3]-now}s left")
            continue
        h, r = send(w3, vault.functions.executeWithdrawal(rid))
        print(f"chain {cid}: executed drain id={rid} tx={h} status={r['status']} deployer bal={w3.eth.get_balance(DEPLOYER.address)/1e18}")


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


RSC_ABI = json.loads("""[
 {"type":"constructor","inputs":[{"name":"registry_","type":"address"}],"stateMutability":"payable"},
 {"type":"function","name":"watchVault","inputs":[{"name":"chainId_","type":"uint256"},{"name":"vault_","type":"address"}],"outputs":[],"stateMutability":"nonpayable"}
]""")
VAULT_CTOR_ABI = json.loads("""[
 {"type":"constructor","inputs":[{"name":"owner_","type":"address"},{"name":"recovery_","type":"address"},{"name":"callbackProxy_","type":"address"},{"name":"callbackSender_","type":"address"},{"name":"waitSeconds_","type":"uint256"},{"name":"largeThreshold_","type":"uint256"},{"name":"instantCap_","type":"uint256"},{"name":"instantWindowSeconds_","type":"uint256"}],"stateMutability":"payable"},
 {"type":"function","name":"deposit","inputs":[],"outputs":[],"stateMutability":"payable"}
]""")
SYS_ABI = json.loads("""[
 {"type":"function","name":"depositTo","inputs":[{"name":"addr","type":"address"}],"outputs":[],"stateMutability":"payable"},
 {"type":"function","name":"reserves","inputs":[{"name":"addr","type":"address"}],"outputs":[{"name":"","type":"uint256"}],"stateMutability":"view"}
]""")


def stage_deploy():
    lasna = w3of(5318007)
    rsc_addr, rsc_tx, rsc_rcpt = deploy_contract(
        lasna, load_bytecode("SentinelReactive"), RSC_ABI, [REGISTRY],
        value=Web3.to_wei(0.8, "ether"),
    )
    print(f"RSC v5: {rsc_addr} tx={rsc_tx} block={rsc_rcpt['blockNumber']} status={rsc_rcpt['status']}")
    # reserves for reactive execution
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
        print(f"Vault v4 chain {cid}: {addr} tx={txh} block={rcpt['blockNumber']} status={rcpt['status']}")
        vaults[str(cid)] = addr
        blocks["vaults"][str(cid)] = rcpt["blockNumber"]
        h, r = send(lasna, rsc.functions.watchVault(cid, addr))
        print(f"  watchVault tx={h} status={r['status']}")

    out = {
        "stack": "v4/v5 (post-audit)",
        "registry": REGISTRY,
        "rsc": rsc_addr,
        "vaults": vaults,
        "deployBlocks": blocks,
    }
    with open(os.path.join(ROOT, "deployments.json.new"), "w") as f:
        json.dump(out, f, indent=2)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    {"drain": stage_drain, "drainx": stage_drainx, "deploy": stage_deploy, "deploy2": stage_deploy2}[sys.argv[1]]()


RSC_V5 = "0x48FA2842cCCbe70EEfD9FE094331af4f932A35A7"
RSC_V5_BLOCK = 8635331


def stage_deploy2():
    """Resume after the RSC v5 deploy (depositTo + vaults + watchVault)."""
    lasna = w3of(5318007)
    sys_c = lasna.eth.contract(address="0x8888888888888888888888888888888888888888", abi=SYS_ABI)
    tx = sys_c.functions.depositTo(RSC_V5).build_transaction({
        "from": DEPLOYER.address,
        "nonce": lasna.eth.get_transaction_count(DEPLOYER.address),
        "gas": 200_000,
        "value": Web3.to_wei(1.0, "ether"),
        "maxFeePerGas": lasna.eth.gas_price * 2,
        "maxPriorityFeePerGas": lasna.eth.gas_price,
    })
    h = lasna.eth.send_raw_transaction(DEPLOYER.sign_transaction(tx).raw_transaction)
    r = lasna.eth.wait_for_transaction_receipt(h, timeout=180)
    print(f"depositTo tx={h.hex()} status={r['status']} reserves={sys_c.functions.reserves(RSC_V5).call()/1e18}")

    vaults, blocks = {}, {"registry": 60039272, "rsc": RSC_V5_BLOCK, "vaults": {}}
    rsc = lasna.eth.contract(address=RSC_V5, abi=RSC_ABI)
    for cid in (84532, 11155111, 1301):
        w3 = w3of(cid)
        addr, txh, rcpt = deploy_contract(
            w3, load_bytecode("GuardedVault"), VAULT_CTOR_ABI,
            [DEPLOYER.address, RECOVERY_ADDR, PROXIES[cid], RSC_V5,
             180, Web3.to_wei(0.004, "ether"), Web3.to_wei(0.008, "ether"), 3600],
            value=Web3.to_wei(FUND[cid], "ether"),
        )
        print(f"Vault v4 chain {cid}: {addr} tx={txh} block={rcpt['blockNumber']} status={rcpt['status']}")
        vaults[str(cid)] = addr
        blocks["vaults"][str(cid)] = rcpt["blockNumber"]
        h2, r2 = send(lasna, rsc.functions.watchVault(cid, addr))
        print(f"  watchVault tx={h2} status={r2['status']}")

    out = {
        "stack": "v4/v5 (post-audit)",
        "registry": REGISTRY,
        "rsc": RSC_V5,
        "vaults": vaults,
        "deployBlocks": blocks,
    }
    with open(os.path.join(ROOT, "deployments.json.new"), "w") as f:
        json.dump(out, f, indent=2)
    print(json.dumps(out, indent=2))


BASE_V4 = "0xA1eDD9dBBAE962B41950F3314660e966bBEa703b"
BASE_V4_BLOCK = 60328343


def stage_deploy3():
    """Sepolia + Unichain vaults only (Base v4 already deployed/watched)."""
    lasna = w3of(5318007)
    rsc = lasna.eth.contract(address=RSC_V5, abi=RSC_ABI)
    vaults = {"84532": BASE_V4}
    blocks = {"registry": 60039272, "rsc": RSC_V5_BLOCK,
              "vaults": {"84532": BASE_V4_BLOCK}}
    for cid, fund in ((11155111, 0.004), (1301, 0.012)):
        w3 = w3of(cid)
        addr, txh, rcpt = deploy_contract(
            w3, load_bytecode("GuardedVault"), VAULT_CTOR_ABI,
            [DEPLOYER.address, RECOVERY_ADDR, PROXIES[cid], RSC_V5,
             180, Web3.to_wei(0.004, "ether"), Web3.to_wei(0.008, "ether"), 3600],
            value=Web3.to_wei(fund, "ether"),
        )
        print(f"Vault v4 chain {cid}: {addr} tx={txh} block={rcpt['blockNumber']} status={rcpt['status']}")
        vaults[str(cid)] = addr
        blocks["vaults"][str(cid)] = rcpt["blockNumber"]
        h2, r2 = send(lasna, rsc.functions.watchVault(cid, addr))
        print(f"  watchVault tx={h2} status={r2['status']}")
    out = {"stack": "v4/v5 (post-audit)", "registry": REGISTRY, "rsc": RSC_V5,
           "vaults": vaults, "deployBlocks": blocks}
    with open(os.path.join(ROOT, "deployments.json.new"), "w") as f:
        json.dump(out, f, indent=2)
    print(json.dumps(out, indent=2))


SEP_V4 = "0x3C17336A3E7f929FEF4608fB053f539dF734B535"
SEP_V4_BLOCK = 12160045


def stage_deploy4():
    """watchVault(Sepolia) + Unichain vault + watchVault + write file."""
    lasna = w3of(5318007)
    rsc = lasna.eth.contract(address=RSC_V5, abi=RSC_ABI)
    h, r = send(lasna, rsc.functions.watchVault(11155111, SEP_V4))
    print(f"watchVault Sepolia tx={h} status={r['status']}")
    w3 = w3of(1301)
    addr, txh, rcpt = deploy_contract(
        w3, load_bytecode("GuardedVault"), VAULT_CTOR_ABI,
        [DEPLOYER.address, RECOVERY_ADDR, PROXIES[1301], RSC_V5,
         180, Web3.to_wei(0.004, "ether"), Web3.to_wei(0.008, "ether"), 3600],
        value=Web3.to_wei(0.012, "ether"),
    )
    print(f"Vault v4 chain 1301: {addr} tx={txh} block={rcpt['blockNumber']} status={rcpt['status']}")
    h2, r2 = send(lasna, rsc.functions.watchVault(1301, addr))
    print(f"  watchVault tx={h2} status={r2['status']}")
    out = {"stack": "v4/v5 (post-audit)", "registry": REGISTRY, "rsc": RSC_V5,
           "vaults": {"84532": BASE_V4, "11155111": SEP_V4, "1301": addr},
           "deployBlocks": {"registry": 60039272, "rsc": RSC_V5_BLOCK,
                            "vaults": {"84532": BASE_V4_BLOCK, "11155111": SEP_V4_BLOCK,
                                       "1301": rcpt["blockNumber"]}}}
    with open(os.path.join(ROOT, "deployments.json.new"), "w") as f:
        json.dump(out, f, indent=2)
    print(json.dumps(out, indent=2))
