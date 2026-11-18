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
  of executing. Queued requests also reserve against the vault balance
  in aggregate, so the queue can never promise out more than the vault
  holds. Splitting a theft into many small withdrawals hits the cap,
  the queue, and the pace guard in turn.
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
      │            (via callback proxy)  │                        │ veto + freeze all 3
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
   from the three vaults, and it enforces the verdicts: LOW → nothing;
   MEDIUM → veto callback to the origin vault; HIGH or a 2nd MEDIUM
   within 1 h → veto of the originating request **plus** freeze
   callbacks to all three vaults. Cross-chain delivery order is not
   guaranteed, so a MEDIUM/HIGH verdict that arrives before its
   request is not dropped: it is flagged `UnverifiedVerdict`, buffered
   as a pending veto, and applied the moment the request appears (a
   HIGH also freezes immediately). Independently, the 11th withdrawal
   request across all vaults within one hour makes the RSC freeze
   everything by itself.
5. Anyone can call `executeWithdrawal` after `readyAt` if the request
   was not vetoed and the vault is not frozen.

## Deployed contracts (testnets)

| Contract | Chain | Address |
|---|---|---|
| VerdictRegistry | Base Sepolia (84532) | `0x0e55C8F84F44336b766Af8469b74d5163abB7F32` |
| SentinelReactive (RSC) | Lasna (5318007) | `0x48FA2842cCCbe70EEfD9FE094331af4f932A35A7` |
| GuardedVault | Base Sepolia (84532) | `0xA1eDD9dBBAE962B41950F3314660e966bBEa703b` |
| GuardedVault | Ethereum Sepolia (11155111) | `0x3C17336A3E7f929FEF4608fB053f539dF734B535` |
| GuardedVault | Unichain Sepolia (1301) | `0x464F45Cf2bF16B1b8E454eaCDD2ff68002E58bce` |

This is the post-audit stack (GuardedVault v4 / SentinelReactive v5,
redeployed 2026-11-18 after a full self-audit; the previous deployment
is listed as superseded in `docs/deployments.md` and its vaults were
drained back to the deployer). The registry was deliberately not
redeployed, so every verdict ever posted stays verifiable against the
same contract.

Live configuration, read from chain with `scripts/print_config.py`
on 2026-11-18 (regenerate it — do not trust this table over the chain):

| chain | vault | balance | waitSeconds | largeThreshold | instantCap / window | frozen |
|---|---|---|---|---|---|---|
| Unichain Sepolia | `0x464F45Cf2bF16B1b8E454eaCDD2ff68002E58bce` | 0.0120 ETH | 180 s | 0.0040 ETH | 0.0080 ETH / 3600 s | False |
| Base Sepolia | `0xA1eDD9dBBAE962B41950F3314660e966bBEa703b` | 0.0200 ETH | 180 s | 0.0040 ETH | 0.0080 ETH / 3600 s | False |
| Ethereum Sepolia | `0x3C17336A3E7f929FEF4608fB053f539dF734B535` | 0.0040 ETH | 180 s | 0.0040 ETH | 0.0080 ETH / 3600 s | False |

RSC `0x48FA2842cCCbe70EEfD9FE094331af4f932A35A7` (Lasna): balance 0.8000 lREACT, reserves 1.0000 lREACT at the same reading.

## Proof — the full loop on-chain

All runs below are from 2026-11-18 against the deployment above, with
the model live (`iforest-3`, hash below) and the queue wait temporarily
set to 60 s so the runs fit in an evening; it was restored to 180 s
afterwards. Full tx list with notes: `docs/deployments.md`.

**Negative tests first — the attacks that must fail, failing:**

| attempt | result |
|---|---|
| Attacker EOA calls `requestWithdrawal` | [tx FAILS](https://sepolia.basescan.org/tx/0xba697361c2be2517115634fe654a33e5d223570adae440face46474a91ea1a0f) — reverts `NotOwner` |
| Owner (daily) key calls `unfreeze` | [tx FAILS](https://sepolia.basescan.org/tx/0x4293eca0440dbc4550be05fd5f036258a73ccf7f53874061019cc3d78b47e37c) — reverts `NotRecovery`; only the recovery key can unfreeze |
| Owner requests a zero-amount withdrawal | [tx FAILS](https://sepolia.basescan.org/tx/0x74a3a519e27ffb8186984d2fabb33e96f529cf72cdf758eb36c4fed2abbd863f) — reverts `ZeroAmount` (v4 input validation) |

**Normal withdrawal executes (fail-open path):**

| step | where | tx |
|---|---|---|
| request 0.008 ETH (queued) | Base | [0xcc8d2059…](https://sepolia.basescan.org/tx/0xcc8d20591294f70ad6892ca0d75d404bdb1356ddeabdf020e4b4c12149aa732a) |
| RSC sees the request (`RequestSeen`) | Lasna | [0x1c5f2266…](https://lasna.reactscan.net/tx/0x1c5f2266203323ef9e85ff0c6fed9378ea8475e9733c8fc7128b8d5c3859b591) |
| verdict LOW (583) | Base | [0xcdfdc918…](https://sepolia.basescan.org/tx/0xcdfdc9182d473717f1b0a33987e963bf578d25702f18cb71f26833051effdfbc) |
| RSC ignores the LOW verdict (`VerdictIgnored`) | Lasna | [0x92c08436…](https://lasna.reactscan.net/tx/0x92c084361f1bcb75d06f1c21c5aeef8208d5bf57317be00be7986291962628ee) |
| executed after the wait | Base | [0xdb81ae9c…](https://sepolia.basescan.org/tx/0xdb81ae9c5c23ebc1fd1894287e53e8de0d31a036b12afe7981f7926e8c91cd3c) |

**Instant cap:** in the burst below, the first three 0.003 ETH
requests were instant-ready; the fourth would have exceeded the
0.008 ETH/h instant budget, so the vault queued it instead
(`readyAt` = request time + wait, readable in the request state of
[0xfb8fd775…](https://sepolia.basescan.org/tx/0xfb8fd7754aeb8a0c39e8aa73857e5b93b8dc140cc1934066e85fd24f14d9d61a)).

**MEDIUM → veto (the burst above, judged live by the model):**

| step | where | tx |
|---|---|---|
| verdict MEDIUM (662) for request 2 | Base | [0x65b2a6a1…](https://sepolia.basescan.org/tx/0x65b2a6a1293b6f82cecc909a293166cd655061ab15f5c38f516a2ccf0709a830) |
| RSC requests the veto (`VetoRequested`) | Lasna | [0x40411f93…](https://lasna.reactscan.net/tx/0x40411f9339d3725e8a1f78c61237e4f577fc0ea651e95fbacae06323555b0bab) |
| veto lands via the callback proxy (`WithdrawalVetoed`) | Base | [0x52726a3b…](https://sepolia.basescan.org/tx/0x52726a3bb36c1171897391465bf88ef2860c7aa14da30671fda37cb4b58e4064) |

**HIGH → veto of the flagged request + pre-emptive freeze of all
three vaults:**

| step | where | tx |
|---|---|---|
| verdict HIGH (713) for request 3 | Base | [0xdafe eea7…](https://sepolia.basescan.org/tx/0xdafe eea7a6ce89c322e234cf445a1ea240ab87ea129913944a14bc280abbad1b) |
| RSC reacts (`VetoRequested` + `FreezeRequested` ×3 in one tx) | Lasna | [0x2fab0dfd…](https://lasna.reactscan.net/tx/0x2fab0dfd99cf4a2560efc31525f3c1668f1fdd873426851d4effaf3b28d0859a) |
| veto callback (request 3) | Base | [0x11683dd2…](https://sepolia.basescan.org/tx/0x11683dd28e780b8459746312c90b14f8e390657db90266f7417b13503d12c2e1) |
| freeze callback | Base | [0xd7d7a15e…](https://sepolia.basescan.org/tx/0xd7d7a15ec52462860f989268ffefc01b935cbaed5754a4e4d55791dc5c579c15) |
| freeze callback | Unichain | [0xc8c929f2…](https://sepolia.unichain.org/tx/0xc8c929f25fbc6b175f4bed64963ec0125b744333cd6993433eb0941dd7ccdb03) |
| freeze callback | Ethereum Sepolia | [0x12da46b2…](https://sepolia.etherscan.org/tx/0x12da46b2c061335fe5ed741a840ab0b9923efd4be055b69c094b4841f4e6adc5) |

The next request scored HIGH again (717) and the RSC vetoed and
froze again — veto/freeze are idempotent, so repeat verdicts do not
revert the loop. Unfreezing was done with the recovery key only (one
tx per vault).

**The audit fix, proven on-chain:** an earlier version of the RSC
froze on HIGH but never vetoed the flagged request itself, so after a
recovery unfreeze the flagged withdrawal — its wait long past — could
still be executed by anyone. The v5 RSC vetoes it in the same reaction.
Proof: after the burst above was unfrozen with the recovery key,
executing the HIGH-flagged request 3
[FAILS](https://sepolia.basescan.org/tx/0x1a46adbf1a74beeb3cc76579a235cd6df14c51e3e5da470e75de795049ac404c)
(reverts `Vetoed`), as does the MEDIUM-vetoed request 2
([tx FAILS](https://sepolia.basescan.org/tx/0x0393cd0ed02ad201283ffdd221a562c388ca7a4b18ee1862e90f05f732ac8f1d)).

**Pace freeze — the RSC acting alone, no verdicts involved:** the
11th withdrawal request inside one hour across the three vaults
([0xc376f55a…](https://sepolia.basescan.org/tx/0xc376f55ab175eb2997c4cbd8b1ad48b92f5cbb9f34724f82c443a6fa7fd8b0e3))
triggered a single Lasna reactive tx carrying `RequestSeen` +
`PaceFreeze` + `FreezeRequested` ×3
([0xd81d1d28…](https://lasna.reactscan.net/tx/0xd81d1d28793290c8cab50dce0a8b1a1ffafca46a33d758a3ed9f6ae4c736be14)),
freezing all three vaults while the worker was down. The worker
judged that request only after it was restarted (HIGH, 685) — the
freeze did not need it.

**Replay:** `scripts/replay.py` was run against Base request 1
(LOW 583), Base request 3 (HIGH 713) and Sepolia request 1
(LOW 571): severity, score, `featuresHash` and `modelHash` all
recomputed from chain data and **MATCH**ed the on-chain verdicts.

### Measured latency (2026-11-18 runs, block timestamps)

- request → verdict posted: **7 s** (the worker's polling cadence
  dominates; the model itself scores in milliseconds)
- verdict → veto/freeze callback landed: **1–9 s** across the three
  chains (Ethereum Sepolia slowest)
- request → all vaults frozen, worst observed: **~16 s**

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
| owner (daily) | deposit; request withdrawals (destination fixed at request time); cancel a pending owner rotation | unfreeze; change settings; veto/freeze | attacker can *request* withdrawals to their own address, but ≥ threshold always queues under the model + RSC, instant flow is capped at 0.008 ETH/h, and 11 requests/h freeze everything. The recovery key can rotate the owner (below) and tighten settings meanwhile. |
| verdictWriter | post verdicts to the registry | move funds; unfreeze; reconfigure | worst case is a freeze DoS (posted HIGHs freeze the vaults). Funds stay put. Recovery: registry owner calls `setVerdictWriter` with a fresh key, recovery key unfreezes the three vaults — 4 transactions, documented in `docs/DECISIONS.md`. |
| recovery (offline) | unfreeze; change wait / threshold / instant cap; propose an owner rotation (48 h delay, owner can cancel, anyone can finalize after the delay) | request withdrawals; move funds; post verdicts | attacker could unfreeze and weaken settings, removing the safety margins — but moving funds still needs the owner key, and the model + RSC keep watching. The recovery address itself is set at deployment and cannot be rotated in place; a compromised recovery key means redeploying the vaults. A merely *lost* owner key no longer strands funds: the recovery key proposes a replacement owner and the rotation finalizes after 48 h unless the (compromised) owner cancels it. |

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
balances and settings as in the table above, RSC reserves 1.0000
lREACT. The worker is a single process; it is kept running during the
event period, and verdicts for any request it missed are posted when
it restarts (the registry rejects duplicates, so restarts are safe).
If the worker is down at any point, the system fails open for queued
withdrawals and the RSC pace guard still applies — both behaviours
are demonstrated in the Proof section.

## Run it

```bash
forge test                                   # 38 unit tests
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
- This stack is the second full revision: after an external design
  review (v3) the contracts went through a full self-audit — an
  independent adversarial review plus a line-by-line re-check — which
  found, among others, that a HIGH verdict froze but never vetoed its
  own request, and that a verdict delivered before its request was
  dropped. All findings were fixed (v4/v5), re-tested (38 tests) and
  re-proven on-chain above; the audit trail is in `docs/DECISIONS.md`.
- Destination-chain gas quirk: on Ethereum Sepolia the vault's
  `requestWithdrawal` measures ~710k gas through the public RPC
  (identical bytecode costs ~150k on Base) — budget gas generously
  there; it is a chain/RPC metering artifact, not contract behaviour.
- Callback `pay()` lets the chain's callback proxy / the Lasna system
  contract pull the delivery fee from the recipient's balance without
  a cap — that is the documented Omni fee model; a cap below the real
  fee would break delivery, so the trust assumption is stated here
  instead (see `src/base/`).
- Earlier deployments of this project exist on the same testnets;
  they are superseded by the table above and are labelled as such in
  `docs/deployments.md` (their vaults were drained back).
- Testnet only. No real funds anywhere in this system.

MIT License.
