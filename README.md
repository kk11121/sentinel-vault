# Sentinel Vault

**An AI-guarded vault where the detection model's key can never touch the funds — and a Reactive contract, not a server, does the stopping.**

Sentinel Vault watches withdrawals from vaults on three chains with a
one-class anomaly model. Every large withdrawal waits in a timelock
queue. The model judges every request and posts its verdict on-chain.
A Reactive Smart Contract (RSC) on Lasna turns verdicts into action:
a MEDIUM verdict vetoes that one withdrawal; a HIGH verdict — or a
second MEDIUM within an hour — freezes **all three vaults pre-emptively**,
before the money moves. If the AI stays silent, withdrawals execute
anyway after the waiting period (**fail-open**): the AI can only stop,
never steal, and never permanently block.

Built for the **Reactive Omni Buildathon — "Reactive Meets AI" track**.

## Why this design

- **Least privilege for the AI.** The verdict-writer key can only post
  verdicts to a registry. Veto/freeze are callable *only* through each
  chain's Reactive callback proxy with the RSC as the injected sender.
  A leaked AI key can cause a freeze (recoverable, owner unfreezes) —
  it can never move a single wei.
- **Reactive, not a cron job.** The freeze/veto path is executed by the
  RSC reacting to on-chain verdict events across chains. There is no
  central automation server in the enforcement path.
- **Auditable after the fact.** Every verdict carries `featuresHash`
  and `modelHash` (keccak256 of the exact model file, shipped in this
  repo as JSON — no pickle). `scripts/replay.py` recomputes any verdict
  from chain data and checks all four fields.
- **Honest evaluation.** `eval/RESULTS.md` compares the model against
  a fixed-threshold rule on synthetic data and publishes the numbers
  as computed — including where the model loses (it flags more normal
  traffic, and false-HIGHs a large-but-legit transfer). This system is
  *auditable and damage-bounding*, not "trustless".

## How it works

```
 GuardedVault (x3 chains)          VerdictRegistry          SentinelReactive
 Base / Eth Sepolia /              (Base Sepolia)           (Lasna, RSC)
 Unichain Sepolia                        │                        │
      │ WithdrawalRequested              │                        │
      ├──────────────────────────────────┤                        │
      │            worker (off-chain)    │                        │
      │  features -> Isolation Forest    │                        │
      │            └──── postVerdict ───►│ VerdictPosted          │
      │                                  ├─────── event ─────────►│ react()
      │                                  │                        │ LOW: ignore
      │◄──────────── veto callback ──────┼────────────────────────┤ MEDIUM: veto
      │◄──────────── freeze callback ────┼────────────────────────┤ HIGH / 2xMEDIUM:
      │            (via callback proxy)  │                        │ freeze all 3
      │ executeWithdrawal() after readyAt if not vetoed/frozen (fail-open)
```

1. `GuardedVault.requestWithdrawal` queues withdrawals ≥ threshold
   with `readyAt = now + wait` (demo: 180 s, threshold 0.02 ETH);
   smaller ones are ready immediately.
2. The worker computes 6 features (amount vs profile median,
   first-seen destination, interval since last withdrawal, last-hour
   count/sum, balance ratio) and scores them with the Isolation
   Forest in `model/model.json`.
3. `VerdictRegistry.postVerdict` (verdict-writer key only) emits
   `VerdictPosted(requestId, vault, severity, score, featuresHash, modelHash)`.
4. The RSC reacts: LOW → nothing; MEDIUM → veto callback to the origin
   vault; HIGH or a 2nd MEDIUM within 1 h → freeze callbacks to all
   three vaults.
5. Anyone can call `executeWithdrawal` after `readyAt` if the request
   was not vetoed and the vault is not frozen.

## Deployed contracts (testnets)

| Contract | Chain | Address |
|---|---|---|
| VerdictRegistry | Base Sepolia (84532) | `0xEe60c9776CAc32bda21ED7e6cAD1497717B28A12` |
| SentinelReactive (RSC) | Lasna (5318007) | `0x946181Feb969e29cA42aF5dB0b17325CA524262e` |
| GuardedVault | Base Sepolia (84532) | `0xFf25f82b50c0164D815D0d18037afab502D2b926` |
| GuardedVault | Ethereum Sepolia (11155111) | `0x95Fd0764a2f75387F35c8eEAB409aa1410b19b2d` |
| GuardedVault | Unichain Sepolia (1301) | `0x68A10a67C79593d6e4a69AB7Abc5762380Dc5560` |

## Proof — the full loop on-chain

**Normal withdrawal executes (fail-open)** — Base Sepolia vault:
request [0x12042758…](https://sepolia.basescan.org/tx/0x12042758c20a2576a522c3a407a4a8c314f068ba20ad1d06dd08f17476fd723e) →
LOW verdict [0xb293d325…](https://sepolia.basescan.org/tx/0xb293d32564523c6934634b414bfd00c08a9811de105bce45b91cf0c7ae267794) →
executed [0x85f28dcf…](https://sepolia.basescan.org/tx/0x85f28dcff94609345aa0320f1ae4ba4a25a5a1d16f548973d08a3b8dec5a28ad)

**MEDIUM → veto** — Base Sepolia vault:
request [0xfe1728e3…](https://sepolia.basescan.org/tx/0xfe1728e39a9ec4f705b31a3a7eeb83edd461c1e5f35c8408abb9c6fc1a47e3b0) →
MEDIUM verdict [0x015b9161…](https://sepolia.basescan.org/tx/0x015b91617be393bb0fee65c4d7b8654712cb568ac9129718922026c8f841f3a5) →
`withdrawals(4).vetoed == true`; executing it reverts `Vetoed`.

**2nd MEDIUM → escalation freeze on all 3 chains** — Base Sepolia vault:
request [0xcddd23b4…](https://sepolia.basescan.org/tx/0xcddd23b45eeb463476be32c75d39b10737b79e052a10a46535ffc524e1ce755a) →
MEDIUM verdict [0x10ee2449…](https://sepolia.basescan.org/tx/0x10ee24497ed134e82b556b4811b30e37a2d4e81830eda8fd1724ec6508688377) →
`frozen() == true` verified on all three vaults.

**Model verdict + replay (M3)** — Ethereum Sepolia vault:
request [0x47f65beb…](https://sepolia.etherscan.org/tx/0x47f65beb7a14aa3b4e863666740c2d5043b5d6b2af6e53126f5c253d5325b4e0) →
model MEDIUM (603) [0xbe2be196…](https://sepolia.basescan.org/tx/0xbe2be1969291db2187c55d7d20ddb9a7d41717a15b05c6b5aeee75a51eabef77) →
vetoed on-chain; `scripts/replay.py` reproduces severity, score,
featuresHash and modelHash exactly.

**HIGH → cross-chain freeze (M1)**: HIGH verdict
[0xdb7859e6…](https://sepolia.basescan.org/tx/0xdb7859e62dcfb39886b8379ee8717be8597fcb2e48ca08e8c6da8fb2ff194ce3) →
vault frozen on Ethereum Sepolia
[0xd2e55797…](https://sepolia.etherscan.org/tx/0xd2e557978361c86538974c279650b8af5272e7dbba2c9245ab9e7ef2316072d4)
(~50 s end-to-end). A direct `freeze()` call from an attacker EOA
reverts, as it must:
[0x29d7d063…](https://sepolia.etherscan.org/tx/0x29d7d0639cc3c018570f4f6b5794ef0732ef22cffffa04b63c6d143458305ae8) (failed tx, expected).

## The model

One-class Isolation Forest trained **only on synthetic normal
behaviour** (disclosed; generator + fixed seeds in `model/`). Exported
as JSON and scored by a pure-python implementation — the same code
path in the worker and in replay. Features, thresholds, limitations
(including the false-alarm cases) are documented in
[`model/MODEL_CARD.md`](model/MODEL_CARD.md); the rule-vs-model
comparison is in [`eval/RESULTS.md`](eval/RESULTS.md).

`modelHash = 0xc65a9db604e61be432fe2822e9cbcdfd97f75698593372377b1987dc5b5f6bb7`

## Run it

```bash
forge test                                   # 10 unit tests
.venv/bin/python model/train.py              # regenerate model.json + hash
.venv/bin/python eval/run_eval.py            # regenerate eval/RESULTS.md
.venv/bin/python worker/worker.py            # live verdict worker
.venv/bin/python scripts/replay.py --chain 11155111 --request-id 1
```

## Repo layout

- `src/contracts/` — GuardedVault, VerdictRegistry, SentinelReactive
- `src/base/` — minimal Omni (post-migration) Reactive base contracts
- `worker/` — off-chain feature computation + model scoring + verdict posting
- `model/` — features, synthetic data generator, training, JSON model, card
- `eval/` — rule-vs-model evaluation and results
- `scripts/replay.py` — after-the-fact verdict verification
- `docs/` — design decisions, deployment log, troubleshooting notes

## Notes from the build

- Post-Omni Lasna: standard Solidity/Foundry, no RVM. The subscription
  wildcard (`REACTIVE_IGNORE`) is not printed in the docs; the value
  that validators actually match is
  `0xa65f96fc951c35ead38878e0f0b7a3c744a6f5ccc1476b313353ce31712313ad`,
  found by byte-comparing live subscription events (see
  `docs/deployments.md` — it cost us two hours; maybe it saves you some).
- Testnet only. No real funds anywhere in this system.

MIT License.
