# Sentinel Vault

**When a multi-chain treasury's daily hot key is stolen, the thief's first withdrawal on one chain should freeze the vaults on all the others — before the money moves.**

An off-chain model decides; a Reactive contract enforces. The model's
key can post verdicts and nothing else — it cannot move, unfreeze, or
reconfigure the vaults.

Sentinel Vault guards withdrawal vaults on three testnet chains with a
one-class anomaly model (Isolation Forest). The owner key requests a
withdrawal; large ones wait in a timelock queue while the model judges
**every** request and posts its verdict on-chain. A Reactive Smart
Contract (RSC) on Lasna turns verdicts into action: a MEDIUM verdict
vetoes that one withdrawal; a HIGH verdict — or a second MEDIUM within
an hour — freezes **all three vaults pre-emptively**. The RSC also
watches the requests themselves and freezes everything on its own if
the cross-chain request pace exceeds 10 per hour, no verdict involved.
If the AI stays silent, queued withdrawals execute anyway after the
waiting period (**fail-open**): the AI can only stop, never steal, and
never permanently block.

Built for the **Reactive Omni Buildathon — "Reactive Meets AI" track**.

## Why this exists

Hot-wallet key compromise is how the big treasury losses actually
happen. In February 2025, Bybit lost ~$1.5B after its signing flow was
compromised ([FBI IC3 PSA, 2025-02-26](https://www.ic3.gov/PSA/2025/PSA250226)).
In May 2024, DMM Bitcoin lost 4,502.9 BTC (≈ ¥48.2B) in an unauthorized
outflow later attributed to the same actor cluster
([DMM Bitcoin official report, 2024-06-05](https://bitcoin.dmm.com/news/20240605_01)).
In both cases the attacker held a *legitimate* signing path — no
contract bug to patch. What was missing was an independent watcher
that could say "this withdrawal pattern is wrong" and stop the *other*
wallets before they were drained too. That watcher is what this
project builds, with the watcher itself kept unable to touch funds.

## Why this design

- **Least privilege for the AI.** The verdict-writer key can only post
  verdicts to a registry. Veto/freeze are callable *only* through each
  chain's Reactive callback proxy with the RSC as the injected sender.
  A leaked AI key can cause a freeze (recoverable) — it can never
  **move** the funds.
- **A single, minimal-privilege server.** The worker is a single
  off-chain process. If it goes down, withdrawals still execute after
  the timelock (fail-open). If it is compromised, the worst it can do
  is freeze — never move funds. Without Reactive, the worker would
  need freeze keys and gas on three chains. With Reactive, it holds
  one key that can only write a verdict on one chain, and the RSC —
  on-chain, auditable, no server — does the cross-chain enforcement.
  The RSC's own pace guard keeps working even while the worker is down
  (demonstrated below with the worker deliberately stopped).
- **Bounded damage by construction.** Withdrawal requests are
  owner-only and the destination is fixed at request time. Requests
  at or above the threshold always queue; small "instant" withdrawals
  are capped per hour, and any excess is routed into the queue instead
  of executing. Splitting a theft into many small withdrawals hits the
  cap, the queue, and the pace guard in turn.
- **Key separation.** The daily owner key can deposit and request, but
  cannot unfreeze or change any safety setting — those belong to a
  separate recovery key that is kept offline. A stolen daily key
  cannot lift a freeze placed on it.
- **Auditable after the fact.** Every verdict carries `featuresHash`
  and `modelHash` (keccak256 of the exact model file, shipped in this
  repo as JSON — no pickle). `scripts/replay.py` recomputes any
  verdict from chain data and checks all four fields.
- **Honest evaluation.** `eval/RESULTS.md` compares the model against
  a fixed-threshold rule on synthetic data and publishes the numbers
  as computed — including where the model loses. This system is
  *auditable and damage-bounding*, not "trustless".

## How it works

```
 GuardedVault (x3 chains)          VerdictRegistry          SentinelReactive
 Base / Eth Sepolia /              (Base Sepolia)           (Lasna, RSC)
 Unichain Sepolia                        │                        │
      │ WithdrawalRequested              │                        │
      ├──────────────────────────────────┼────── event ──────────►│ react()
      │            worker (off-chain)    │                        │ track request;
      │  features -> Isolation Forest    │                        │ pace > 10/h:
      │            └──── postVerdict ───►│ VerdictPosted          │ freeze all
      │                                  ├─────── event ─────────►│ react()
      │                                  │                        │ LOW: ignore
      │◄──────────── veto callback ──────┼────────────────────────┤ MEDIUM: veto
      │◄──────────── freeze callback ────┼────────────────────────┤ HIGH / 2xMEDIUM:
      │            (via callback proxy)  │                        │ freeze all 3
      │ executeWithdrawal() after readyAt if not vetoed/frozen (fail-open)
```

1. `GuardedVault.requestWithdrawal` (owner only; destination fixed at
   request time) queues withdrawals ≥ threshold with
   `readyAt = now + waitSeconds`. Smaller ones are ready immediately
   but consume a per-window instant budget; a small withdrawal that
   would exceed the budget is queued instead of executing instantly.
2. The worker computes 8 features (amount vs profile median,
   first-seen destination, interval since last withdrawal, last-hour
   count/sum, balance ratio, plus 24-hour count/sum) and scores them
   with the Isolation Forest in `model/model.json`.
3. `VerdictRegistry.postVerdict` (verdict-writer key only) records the
   verdict keyed by `(chainId, vault, requestId)` and emits
   `VerdictPosted`. A second verdict for the same request reverts.
4. The RSC reacts twice over: it tracks every `WithdrawalRequested`
   from the three vaults (verdicts for requests it has never seen are
   flagged `UnverifiedVerdict` — a MEDIUM for an unknown request is
   ignored, a HIGH still freezes), and it enforces the verdicts:
   LOW → nothing; MEDIUM → veto callback to the origin vault; HIGH or
   a 2nd MEDIUM within 1 h → freeze callbacks to all three vaults.
   Independently, the 11th withdrawal request across all vaults within
   one hour makes the RSC freeze everything by itself.
5. Anyone can call `executeWithdrawal` after `readyAt` if the request
   was not vetoed and the vault is not frozen.

## Deployed contracts (testnets)

| Contract | Chain | Address |
|---|---|---|
| VerdictRegistry | Base Sepolia (84532) | `0x0e55C8F84F44336b766Af8469b74d5163abB7F32` |
| SentinelReactive (RSC) | Lasna (5318007) | `0xeaE20eccD1F308CaB3e8a4c99e588D8CC21a1ff8` |
| GuardedVault | Base Sepolia (84532) | `0xAf17d1e294c35cA4eFE35c58B201D6F95Aef3DE4` |
| GuardedVault | Ethereum Sepolia (11155111) | `0x0C0c54778431652a2c6b92E088fB02335d395BED` |
| GuardedVault | Unichain Sepolia (1301) | `0x95Fd0764a2f75387F35c8eEAB409aa1410b19b2d` |

Live configuration, read from chain with `scripts/print_config.py`
on 2026-11-18 (regenerate it — do not trust this table over the chain):

| chain | vault | balance | waitSeconds | largeThreshold | instantCap / window | frozen |
|---|---|---|---|---|---|---|
| Unichain Sepolia | `0x95Fd0764a2f75387F35c8eEAB409aa1410b19b2d` | 0.0120 ETH | 180 s | 0.0040 ETH | 0.0080 ETH / 3600 s | False |
| Base Sepolia | `0xAf17d1e294c35cA4eFE35c58B201D6F95Aef3DE4` | 0.0120 ETH | 180 s | 0.0040 ETH | 0.0080 ETH / 3600 s | False |
| Ethereum Sepolia | `0x0C0c54778431652a2c6b92E088fB02335d395BED` | 0.0080 ETH | 180 s | 0.0040 ETH | 0.0080 ETH / 3600 s | False |

RSC `0xeaE20eccD1F308CaB3e8a4c99e588D8CC21a1ff8` (Lasna): balance 1.5000 lREACT, reserves 0.6611 lREACT at the same reading.

## Proof — the full loop on-chain

All runs below are from 2026-11-18 against the deployment above, with
the model live (`iforest-3`, hash below) and the queue wait temporarily
set to 60 s so the runs fit in an evening; it was restored to 180 s
afterwards. Full tx list with notes: `docs/deployments.md`.

**Negative tests first — the attacks that must fail, failing:**

| attempt | result |
|---|---|
| Attacker EOA calls `requestWithdrawal` | [tx FAILS](https://sepolia.basescan.org/tx/0xf1d85a7b8bc8c30d99852d79f18bf1e9287631649b7bfb1ce83f2843512ebbfb) — reverts `NotOwner` |
| Owner (daily) key calls `unfreeze` on a frozen vault | [tx FAILS](https://sepolia.basescan.org/tx/0xe04e96ab3dd5199cc93c0dd7e7ee997ac262185588acffdf4c2bae754aec056c) — reverts `NotRecovery`; only the recovery key can unfreeze |
| 7th rapid request while frozen | [tx FAILS](https://sepolia.etherscan.org/tx/0x072d04154749d14111b54afc369f2f776a04b9f8604d4ca725f7db06b74947d3) — reverts `VaultFrozen` |

**Normal withdrawal executes (fail-open path):**

| step | where | tx |
|---|---|---|
| request 0.008 ETH (queued) | Base | [0xeebd5b7e…](https://sepolia.basescan.org/tx/0xeebd5b7e694dd1ecf234a31c69800cb4e6168a57264225fa39c24b77774978da) |
| RSC sees the request (`RequestSeen`) | Lasna | [0x4dfa549d…](https://lasna.reactscan.net/tx/0x4dfa549d1f658a2bd554ceb2e757b74dbefda8fa7b53cad379e2200fb942a3b7) |
| verdict LOW (583) | Base | [0xd9566a09…](https://sepolia.basescan.org/tx/0xd9566a099b529eb0a4a781b161d9ca82a5e9536f56d18f97a623fc1a6d6d17b8) |
| RSC ignores the LOW verdict (`VerdictIgnored`) | Lasna | [0x41b8f051…](https://lasna.reactscan.net/tx/0x41b8f05187b1f9a0dc13f3dde061be427ddd3ece51c7e568e9fe3d5a1fe1761c) |
| executed after the wait | Base | [0x15edb14c…](https://sepolia.basescan.org/tx/0x15edb14cc5393733e86372b61cde3f8c87d7d7650fac692040fe17576e2cb6be) |

**Instant cap:** three 0.003 ETH requests in seconds — the first two
were ready immediately; the third would have exceeded the 0.008 ETH/h
instant budget, so the vault queued it instead (`readyAt` = request
time + wait, readable in the request state of
[0x95c86a51…](https://sepolia.basescan.org/tx/0x95c86a5130217b841f5f41e7ec19f2d17714f5e747c357b1a9df1b6caea00bdc)).

**MEDIUM → veto (the burst above, judged live by the model):**

| step | where | tx |
|---|---|---|
| verdict MEDIUM (662) for request 2 | Base | [0xc928d167…](https://sepolia.basescan.org/tx/0xc928d167388426fc77f437a4cd60fcaecfb54df74147984021b820d717d2e88a) |
| RSC requests the veto (`VetoRequested`) | Lasna | [0x3058ab3d…](https://lasna.reactscan.net/tx/0x3058ab3d4474042e4ff045abfac5611be32290287c5faa705a990e9bda91a0b4) |
| veto lands via the callback proxy (`WithdrawalVetoed`) | Base | [0xa5c2bc1c…](https://sepolia.basescan.org/tx/0xa5c2bc1c8c291860a9d7afe6e25714106d1bb81a086f225f12cbf7a4da4897a3) |

A second MEDIUM veto, on Ethereum Sepolia: verdict
[0x72f21003…](https://sepolia.basescan.org/tx/0x72f21003e798f377ec6ded77d2afd09f45a4ebca59fab9f89f0ed2f565d066e0)
(647) → `withdrawals(2).vetoed == true` on the Sepolia vault.

**HIGH → pre-emptive freeze of all three vaults:**

| step | where | tx |
|---|---|---|
| verdict HIGH (713) for request 3 | Base | [0xa0ee51c8…](https://sepolia.basescan.org/tx/0xa0ee51c8d547a8d1630b7a2108005d9c2595d4b48070e2d99192126bc9f559bc) |
| RSC requests freezes (`FreezeRequested` ×3) | Lasna | [0x2e415642…](https://lasna.reactscan.net/tx/0x2e4156422a237d9234fd0eeb2b902ea2484aacb429f86e9e66da42dbcac98027) |
| freeze callback | Base | [0xce4bd474…](https://sepolia.basescan.org/tx/0xce4bd4742251bebd2e616c6a846abb6416d419d4af3f6b350f8a5b7d4bf2acb4) |
| freeze callback | Unichain | [0x1f3600be…](https://sepolia.unichain.org/tx/0x1f3600be20a360e8792d6775b78ffb9baac9ad56a6bf5b89076928c2e3d28d35) |
| freeze callback | Ethereum Sepolia | [0x68a8b1b2…](https://sepolia.etherscan.org/tx/0x68a8b1b2f129eae8ace86a9eaaeb93b322394e74298a8365745a595fca9ba090) |

The next request scored HIGH again (717) and the RSC froze again —
veto/freeze are idempotent, so repeat verdicts do not revert the loop.
Unfreezing was done with the recovery key only (one tx per vault).

**Pace freeze — the RSC acting alone, worker stopped:** with the
worker deliberately shut down, the 11th withdrawal request inside one
hour across the three vaults
([0x0af58b70…](https://sepolia.basescan.org/tx/0x0af58b70933a5ac581a27c69aa8f709ecb6aaad234095a6a7545b6a9a47aa2f1))
triggered a single Lasna reactive tx carrying `RequestSeen` +
`PaceFreeze` + `FreezeRequested` ×3
([0xf5aeb1e9…](https://lasna.reactscan.net/tx/0xf5aeb1e9e1603adbc90b695e10241d1e540a25692cea8ebe0283621b0eaf0fbc)),
and freeze callbacks landed on
[Base](https://sepolia.basescan.org/tx/0x98bfb7b81bc7d90c776fd8cd21a9b5b9de1fc6524ea542765db67e69126814d7),
[Unichain](https://sepolia.unichain.org/tx/0xd6b22bc1d072217978c99d7e615b0fc69708966c10bcdb483d5c93ef2dff82ac) and
[Sepolia](https://sepolia.etherscan.org/tx/0xcce2cf3e2ccb90333d8c01a0d1ed007b86c5f5ebc9506709e8d5102c6721ab84)
within 6 seconds. No AI verdict was involved — the worker only judged
that request after it was restarted (LOW, 522).

**Replay:** `scripts/replay.py` was run against Base request 1
(LOW 583), Base request 3 (HIGH 713) and Sepolia request 2
(MEDIUM 647): severity, score, `featuresHash` and `modelHash` all
recomputed from chain data and **MATCH**ed the on-chain verdicts.

### Measured latency (2026-11-18 runs, block timestamps)

- request → verdict posted: **10 s** (the worker's polling cadence
  dominates; the model itself scores in milliseconds)
- verdict → veto/freeze callback landed: **1–7 s** across the three
  chains
- request → all vaults frozen, worst observed: **~17 s**

That is why `waitSeconds` is 180 s in the deployed configuration:
roughly **10× the worst observed end-to-end loop**, so a veto or freeze
has ample time to land before a queued withdrawal can execute. Two
honest limits follow: a veto only works on *queued* withdrawals (an
instant withdrawal inside the cap can execute before any verdict —
that is exactly what the cap and the pace guard bound), and the
180 s wait is a demo value; a production treasury would use hours.

## If a key leaks — who can do what

| key | can do | cannot do | if compromised |
|---|---|---|---|
| owner (daily) | deposit; request withdrawals (destination fixed at request time) | unfreeze; change settings; veto/freeze | attacker can *request* withdrawals to their own address, but ≥ threshold always queues under the model + RSC, instant flow is capped at 0.008 ETH/h, and 11 requests/h freeze everything. Rotate the owner and let the recovery key tighten settings meanwhile. |
| verdictWriter | post verdicts to the registry | move funds; unfreeze; reconfigure | worst case is a freeze DoS (posted HIGHs freeze the vaults). Funds stay put. Recovery: registry owner calls `setVerdictWriter` with a fresh key, recovery key unfreezes the three vaults — 4 transactions, documented in `docs/DECISIONS.md`. |
| recovery (offline) | unfreeze; change wait / threshold / instant cap | request withdrawals; move funds; post verdicts | attacker could unfreeze and weaken settings, removing the safety margins — but moving funds still needs the owner key, and the model + RSC keep watching. The recovery address is set at deployment and cannot be rotated in place; a compromised recovery key means redeploying the vaults. |

Disclosure: because MEDIUM×2 escalates, a leaked verdictWriter — or
just a burst of borderline traffic — can freeze all three vaults
cheaply. That is deliberate: freezing is the safe direction, it is
always recoverable by the recovery key, and the alternative (a freeze
that needs a human to approve) would not land in time.

## The model

One-class Isolation Forest trained **only on synthetic normal
behaviour** (disclosed; generator + fixed seeds in `model/`). The
current model is `iforest-3`: 8 features, including 24-hour pace
aggregates added after probing showed a slow drain (20 small
withdrawals to an already-known address) scored LOW forever under the
previous model — v3 flags it at step 2. Exported as JSON and scored by
a pure-python implementation — the same code path in the worker and in
replay. Features, thresholds, version history and limitations are in
[`model/MODEL_CARD.md`](model/MODEL_CARD.md); the rule-vs-model
comparison (two vault profiles, false-positive costs counted, residual
risks stated) is in [`eval/RESULTS.md`](eval/RESULTS.md).

`modelHash = 0x0dfa7cb105d6c64d39889abc4926fc514b0cccf075c9e3071ddff893fcfd45c5`

The known-destination list the worker scores against is committed at
`worker/known_destinations.json` — replay from a clean clone uses the
same list, so verdicts reproduce exactly.

## Status during judging

Last verified on-chain: **2026-11-18** — all three vaults unfrozen,
balances and settings as in the table above, RSC reserves 0.6611
lREACT. The worker is a single process; it is kept running during the
event period, and verdicts for any request it missed are posted when
it restarts (the registry rejects duplicates, so restarts are safe).
If the worker is down at any point, the system fails open for queued
withdrawals and the RSC pace guard still applies — both behaviours
are demonstrated in the Proof section.

## Run it

```bash
forge test                                   # 23 unit tests
.venv/bin/python model/train_v3.py           # regenerate model.json + hash
.venv/bin/python eval/run_eval.py            # regenerate eval/RESULTS.md
.venv/bin/python worker/worker.py            # live verdict worker
.venv/bin/python scripts/replay.py --chain 84532 --request-id 3
.venv/bin/python scripts/print_config.py     # live config table from chain
```

## Repo layout

- `src/contracts/` — GuardedVault, VerdictRegistry, SentinelReactive
- `src/base/` — minimal Omni (post-migration) Reactive base contracts,
  reimplemented from the documented API (the public reactive-lib still
  targets the legacy RVM)
- `worker/` — off-chain feature computation + model scoring + verdict
  posting; `known_destinations.json` is the committed scoring context
- `model/` — features, synthetic data generator, training, JSON
  models (v1–v3 kept), model card
- `eval/` — rule-vs-model evaluation and results
- `scripts/` — replay verification, live config printer, evidence
  helpers used for the runs above
- `deployments.json` — the live deployment the worker/replay load
- `docs/` — design decisions, deployment + evidence log,
  troubleshooting notes

## Notes from the build

- Post-Omni Lasna: standard Solidity/Foundry, no RVM. The subscription
  wildcard (`REACTIVE_IGNORE`) is not printed in the docs; the value
  that validators actually match is
  `0xa65f96fc951c35ead38878e0f0b7a3c744a6f5ccc1476b313353ce31712313ad`,
  found by byte-comparing live subscription events (see
  `docs/deployments.md` — it cost us two hours; maybe it saves you some).
- Destination-chain callback fees are paid from each vault's own
  balance (the callback proxy calls `pay()` on the recipient); the
  system-contract address has no code on the destination chains, so
  "reserves" deposits there would just be transfers to a dead address.
- Earlier (pre-review) deployments of this project exist on the same
  testnets; they are superseded by the table above and are labelled
  "v0 (pre-fix)" in `docs/deployments.md`.
- Testnet only. No real funds anywhere in this system.

MIT License.
