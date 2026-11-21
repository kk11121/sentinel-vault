# Sentinel Vault

**When a multi-chain treasury's daily hot key is stolen: the thief's first anomalous withdrawal is vetoed; by the second, the vaults on every chain are frozen — before any queued withdrawal can execute.**

An off-chain model decides; a Reactive contract enforces. The model's
key can post verdicts and nothing else — it cannot move, unfreeze, or
reconfigure the vaults.

Sentinel Vault guards withdrawal vaults on three testnet chains with a
one-class anomaly model (Isolation Forest). The owner key requests a
withdrawal; large ones wait in a timelock queue while the model judges
**every** request and posts its verdict on-chain. A Reactive Smart
Contract (RSC) on Lasna turns verdicts into action: a MEDIUM verdict
vetoes that one withdrawal; a HIGH verdict — or a second MEDIUM within
an hour — freezes **all three vaults pre-emptively**. A verdict
delivered before its request is not dropped either: the RSC buffers
it and applies it the moment the request appears, because
cross-chain delivery order is not guaranteed. The RSC also
watches the requests themselves and freezes everything on its own if
the cross-chain request pace exceeds 10 per fixed one-hour window,
no verdict involved.
If the AI stays silent, queued withdrawals execute anyway after the
waiting period (**fail-open**): the AI can only stop, never steal, and
never permanently block.

Built for the **Reactive Omni Buildathon — "Reactive Meets AI" track**.

## For judges: the 60-second check

1. **One cross-chain freeze, end to end.** Base request 2 scored
   HIGH (735):
   [verdict](https://sepolia.basescan.org/tx/0x5d192de11fb1cf251c67b29a381c60fa28685d56d8a0997ba638654369aad3ae)
   → [RSC reaction on Lasna](https://lasna.reactscan.net/tx/0xfe429e3c9831b9a4b2ae045a2629974fe80afe6c7a211d0f591c5e4814b720a2)
   (veto + FreezeRequested ×3) → freeze callbacks on
   [Base](https://sepolia.basescan.org/tx/0xf8393de45fa91bfa65492145a419be8d629bce2e6f3ce561bf4748c0b365ee03),
   [Ethereum Sepolia](https://sepolia.etherscan.io/tx/0xfa750ebbcc8eca022dcbaefb6942e2c4256c1b7476fc4ee96c21625b98c0565c)
   and
   [Unichain Sepolia](https://sepolia.uniscan.xyz/tx/0x78f074180abb4d3a85dc7f2ee44e34cfea5950d666bf7567c00e0cb4e2930c85).
   Request → all three vaults frozen took ~12 s here; the worst
   observed across all runs is ≈17 s (`docs/deployments.md`).
2. **The attacks that must fail, failing.** The negative-test
   table at the top of [Proof](#proof--the-full-loop-on-chain)
   below — five attempts, five named reverts, read from the live
   vaults; the full evidence log is `docs/deployments.md`.
3. **Still alive during judging.** The
   [VerdictRegistry event history](https://sepolia.basescan.org/address/0x0e55C8F84F44336b766Af8469b74d5163abB7F32)
   lists every verdict ever posted; the latest one's timestamp is
   the worker's pulse (see "Status during judging").

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
  are capped per fixed one-hour window, and any excess is routed into
  the queue instead of executing. Queued requests also reserve against
  the vault balance in aggregate, so the queue can never promise out
  more than the vault
  holds. Splitting a theft into many small withdrawals hits the cap,
  the queue, and the pace guard in turn.
- **Key separation.** The daily owner key can deposit and request, but
  cannot unfreeze or change any safety setting — those belong to a
  separate recovery key. In production the recovery key is kept
  offline; in this testnet demo it sits on the operator machine so
  the evidence runs could unfreeze. A stolen daily key cannot lift
  a freeze placed on it.
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
      │  features -> Isolation Forest    │                        │ pace > 10/fixed 1h window:
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
   was not vetoed and the vault is not frozen. The requester (or the
   recovery key) can instead `cancelWithdrawal` while the request is
   live, which releases its reservation. The RSC ignores verdicts
   that name a (chain, vault) pair it does not watch, and counts
   each withdrawal log exactly once, so duplicated deliveries can
   neither trigger enforcement nor inflate the pace guard.

## Deployed contracts (testnets)

| Contract | Chain | Address |
|---|---|---|
| VerdictRegistry | Base Sepolia (84532) | `0x0e55C8F84F44336b766Af8469b74d5163abB7F32` |
| SentinelReactive (RSC) | Lasna (5318007) | `0x00eC75c154EF87A38836819594c0F2898cF3Eb06` |
| GuardedVault | Base Sepolia (84532) | `0x1Eb81CC9a9b9760D1DA575C268c47f727369c6f4` |
| GuardedVault | Ethereum Sepolia (11155111) | `0xd8D640DeEcD14DA46b78e29285cdc682BA118Ad6` |
| GuardedVault | Unichain Sepolia (1301) | `0xAf17d1e294c35cA4eFE35c58B201D6F95Aef3DE4` |

This is the current stack (GuardedVault v5 / SentinelReactive v6).
It redeployed the post-audit stack (v4/v5) after a second adversarial
review: the RSC now ignores verdicts that name a (chain, vault) pair
it does not watch, counts each withdrawal log exactly once, and the
vault gained a per-request `cancelWithdrawal`. Earlier deployments
are listed as superseded in `docs/deployments.md` and their vaults
were drained back to the deployer. The registry was deliberately not
redeployed, so every verdict ever posted stays verifiable against
the same contract.

Live configuration, read from chain with `scripts/print_config.py`
on 2026-11-18 (regenerate it — do not trust this table over the chain):

| chain | vault | balance | waitSeconds | largeThreshold | instantCap / window | frozen |
|---|---|---|---|---|---|---|
| Unichain Sepolia | `0xAf17d1e294c35cA4eFE35c58B201D6F95Aef3DE4` | 0.0023 ETH | 180 s | 0.0040 ETH | 0.0080 ETH / 3600 s | False |
| Base Sepolia | `0x1Eb81CC9a9b9760D1DA575C268c47f727369c6f4` | 0.0110 ETH | 180 s | 0.0040 ETH | 0.0080 ETH / 3600 s | False |
| Ethereum Sepolia | `0xd8D640DeEcD14DA46b78e29285cdc682BA118Ad6` | 0.0120 ETH | 180 s | 0.0040 ETH | 0.0080 ETH / 3600 s | False |

RSC `0x00eC75c154EF87A38836819594c0F2898cF3Eb06` (Lasna): balance 0.8000 lREACT, reserves 1.0200 lREACT at the same reading (reserves are drawn down by each reactive transaction, roughly 0.01 lREACT per callback cycle, and were topped up on 2026-11-18). The Unichain vault's small balance is deliberate for this run: the deployer's Unichain faucet funds were nearly exhausted, and its evidence only needed small requests. (The Unichain balance above includes a 0.002 ETH top-up on 2026-11-21, tx [0x209f84b9…](https://sepolia.uniscan.xyz/tx/0x209f84b956514d521c7ac552f4a9d69945d3d2f839f4c653e2329aa6ff50c04e), so the vault can keep paying callback fees during judging.)

## Proof — the full loop on-chain

All runs below are from 2026-11-18 against the deployment above,
with the model live (`iforest-3`, hash below). Full tx list with
notes: `docs/deployments.md`.

**Negative tests first — the attacks that must fail, failing**
(read via `eth_call` against the live vaults; each reverts with the
named error):

| attempt | result |
|---|---|
| Attacker EOA calls `requestWithdrawal` | reverts `NotOwner` |
| Owner (daily) key calls `unfreeze` | reverts `NotRecovery`; only the recovery key can unfreeze |
| Owner requests a zero-amount withdrawal | reverts `ZeroAmount` |
| Stranger calls `cancelWithdrawal` on a live request | reverts `NotRequester` |
| Third 0.004 ETH burst request in a row | reverts `InsufficientBalance` — earlier queued requests reserve against the balance in aggregate, so the queue cannot over-promise |

**Normal withdrawal executes (fail-open path):**

| step | where | tx |
|---|---|---|
| request 0.001 ETH to the owner | Base | [0xa2cd8b68…](https://sepolia.basescan.org/tx/0xa2cd8b68b61ad93e625eff3e301ea114fad397efed63584fda07b7dba6c9bad1) |
| RSC sees the request (`RequestSeen`) | Lasna | [0x589c68f6…](https://lasna.reactscan.net/tx/0x589c68f64444d44da62add21a7376c49d01ae7558bf6ee12210a3d4b06650907) |
| verdict LOW (522), 11 s after the request | Base | [0x6f3da7d6…](https://sepolia.basescan.org/tx/0x6f3da7d62fbaf6d31561140743520b47f4457fefffb3a4a8b4c83386c3480a59) |
| executed | Base | [0xbaa2fa62…](https://sepolia.basescan.org/tx/0xbaa2fa62505484a764f7ad955c6e040d5cc7460e2710d64c39388dc38cee4e23) |

The same loop ran on Unichain Sepolia: request 0.0005 ETH
([0xec06a071…](https://sepolia.uniscan.xyz/tx/0xec06a071c6b9107d26fb6906cf0c6ec0f3a5886ad520a24bd08c06c69ccfdb88))
→ LOW (611)
([0xf2f3827d…](https://sepolia.basescan.org/tx/0xf2f3827da97fdc4a0fae293e1e1cb7d2956c564eebd2be00f4f38b10ca041469))
→ executed
([0x857caa44…](https://sepolia.uniscan.xyz/tx/0x857caa44e38d9f09e3a43e3cb24053a560e066f54167e52c1612f17873618483)).

**MEDIUM → veto only, no freeze (Ethereum Sepolia):** request 2
(0.001 ETH to the owner;
[0xb8b18050…](https://sepolia.etherscan.io/tx/0xb8b18050a72f56ef146e94755fd7cfe37360394012c9c53e4cbd20179784c14b))
scored MEDIUM (624)
([0x98ef6e72…](https://sepolia.basescan.org/tx/0x98ef6e728f86a251dc807aaebbe5a6c18c76c30936d9b8987e38df5327a17716),
40 s after the request) and was vetoed via the callback proxy
([0x9c2206e5…](https://sepolia.etherscan.io/tx/0x9c2206e572e6eed55e02b0795137e8bc334c4d894aed508c675e370f05b9cf01)).
All three vaults were read back unfrozen immediately after — a
MEDIUM touches exactly one request.

**Escalation, live:** the next Sepolia request scored MEDIUM again
(627;
[0x24ecf115…](https://sepolia.basescan.org/tx/0x24ecf1156640dc778e0ed81266ce670a7390311820b3efc047444ca4b02724cc)).
As the second MEDIUM for the same vault within one hour, the RSC
escalated it — veto plus freeze-all, `Escalated` event in
[0xb931eedf…](https://lasna.reactscan.net/tx/0xb931eedff1fe486247c331a9cc363171280e4c42bf0125e51660abf60e847311).
That escalation's freeze callbacks landed on all three chains:
Base
([0x26c03c06…](https://sepolia.basescan.org/tx/0x26c03c06ea438357b600fa93c392ba5f3ec2914399000b29bcfa6877c2eeb57d)),
Ethereum Sepolia
([0xa273c552…](https://sepolia.etherscan.io/tx/0xa273c5523fff4ffb5edbc03a9f28f29c594b5499271e4489616d4dd1afb1eaee))
and Unichain Sepolia
([0xb3fad0a9…](https://sepolia.uniscan.xyz/tx/0xb3fad0a98f2c23ea7ebd72cc0367c88bc47128a22f2121843e0daf96554874ce)).

**HIGH → veto of the flagged request + pre-emptive freeze of all
three vaults (Base):** requests to a first-seen destination scored
HIGH (735) and HIGH (714):

| step | where | tx |
|---|---|---|
| verdict HIGH (735) for request 2 | Base | [0x5d192de1…](https://sepolia.basescan.org/tx/0x5d192de11fb1cf251c67b29a381c60fa28685d56d8a0997ba638654369aad3ae) |
| RSC reaction (veto + FreezeRequested ×3) | Lasna | [0xfe429e3c…](https://lasna.reactscan.net/tx/0xfe429e3c9831b9a4b2ae045a2629974fe80afe6c7a211d0f591c5e4814b720a2) |
| veto callback (request 2) | Base | [0x9c981fc1…](https://sepolia.basescan.org/tx/0x9c981fc16bf685444d6408f376f6ebfbbb2b16bf60c26f2fe5c4bd09435cfaec) |
| freeze callback | Base | [0xf8393de4…](https://sepolia.basescan.org/tx/0xf8393de45fa91bfa65492145a419be8d629bce2e6f3ce561bf4748c0b365ee03) |
| freeze callback (same verdict) | Ethereum Sepolia | [0xfa750ebb…](https://sepolia.etherscan.io/tx/0xfa750ebbcc8eca022dcbaefb6942e2c4256c1b7476fc4ee96c21625b98c0565c) |
| freeze callback (same verdict) | Unichain Sepolia | [0x78f07418…](https://sepolia.uniscan.xyz/tx/0x78f074180abb4d3a85dc7f2ee44e34cfea5950d666bf7567c00e0cb4e2930c85) |
| verdict HIGH (700) for Sepolia request 1 | Base | [0x583e8b1c…](https://sepolia.basescan.org/tx/0x583e8b1c7c0e3d0eec4fdb665de33a21c12cda614ca28f5f670cd6602d6f5945) |

All three freeze callbacks above followed the single HIGH (735)
verdict within 8 seconds (Base +2 s, Unichain +3 s, Ethereum
Sepolia +8 s, block timestamps) — one verdict, three chains
frozen.

**The v5 audit fix, proven again on this stack:** after a recovery
unfreeze, executing the HIGH-flagged Base request 2
[FAILS](https://sepolia.basescan.org/tx/0x66bc581d4dbf3150542f58659082eeed6bd6e81e6082ed109dec5188b7dd7346)
(reverts `Vetoed`) — a HIGH verdict vetoes its own request, it does
not merely pause it.

**Verdicts about unwatched vaults are ignored (new in v6):** the
verdict writer posted a HIGH verdict (score 999) naming the
*previous* stack's Base vault — a real vault with registry history,
but not one this RSC watches
([0xc3515b45…](https://sepolia.basescan.org/tx/0xc3515b45ad174d3a13168342845a53af753cc4b370c05e23484646d5402fb92e)).
The RSC answered with a single `VerdictForUnwatched` event
([0x9a57eec6…](https://lasna.reactscan.net/tx/0x9a57eec68dfcf9c31baf519f3d7e61e72247893b5e0e68977bc6176d4abc7abe))
and did nothing else; every vault stayed unfrozen. Under the
previous RSC the same verdict would have frozen all three vaults.

**Per-request cancel (new in v5):** Base request 6 (0.005 ETH,
queued) held a 0.005 ETH reservation. The owner cancelled it
([0x0e811f66…](https://sepolia.basescan.org/tx/0x0e811f6624f1835abc9ecfc782cc69e7aef9ba9b69b04118e9a660a30f26f254))
and `pendingTotal` returned to 0; executing it afterwards reverts
`Cancelled`. (The worker later scored the cancelled request HIGH
from its burst-era features; the resulting veto callback is a
no-op on a cancelled request, as designed.)

**Pace freeze — the RSC acting alone, worker deliberately stopped:**
with the worker shut down (verified stopped before the run), the
11th withdrawal request inside one hour across the vaults triggered
a single Lasna reactive tx carrying `RequestSeen` + `PaceFreeze` +
`FreezeRequested` ×3
([0x81c35c28…](https://lasna.reactscan.net/tx/0x81c35c2827a84a669db73ffdc691c20acbe9d4869884112442f08f6366c54aff)),
and the freeze callback landed on Base in
[0xf3349ce5…](https://sepolia.basescan.org/tx/0xf3349ce5491c6d78cebbe38fad90635d9703ebc170ea8d240da7936a8182191d).
No AI verdict was involved in the freeze.

**Worker retry, live:** the worker's first verdict post for Base
request 5 failed with a nonce conflict (a second process had used
the same writer key for the unwatched-verdict proof above). The
worker marked it unposted, and after a process restart re-posted it
successfully — HIGH (713),
[0xa2e587dd…](https://sepolia.basescan.org/tx/0xa2e587dd91de4f150ef831bfb5643b0b48df058d248557e29ef1039b86398b63).
No verdict was lost.

**Replay:** `scripts/replay.py` was run against Base request 1
(LOW 522), Base request 2 (HIGH 735), Sepolia request 1 (HIGH 700)
and Sepolia request 2 (MEDIUM 624): severity, score, `featuresHash`
and `modelHash` all recomputed from chain data and **MATCH**ed the
on-chain verdicts. Base request 2 also replays to a MATCH from a
clean clone with no `.env` present.

### Measured latency (2026-11-18 runs, block timestamps)

- request → verdict posted: **11 s** on Base, **40 s** on Ethereum
  Sepolia (the worker's polling cadence dominates; the model itself
  scores in milliseconds)
- verdict → veto/freeze callback landed: seconds per chain, as in
  the runs above

That is why `waitSeconds` is 180 s in the deployed configuration:
an order of magnitude above the observed end-to-end loop, so a veto
or freeze has ample time to land before a queued withdrawal can
execute. Two honest limits follow: a veto only works on *queued*
withdrawals (an instant withdrawal inside the cap can execute
before any verdict — that is exactly what the cap and the pace
guard bound), and the 180 s wait is a demo value; a production
treasury would use hours.

## If a key leaks — who can do what

| key | can do | cannot do | if compromised |
|---|---|---|---|
| owner (daily) | deposit; request withdrawals (destination fixed at request time); cancel its own queued withdrawals; cancel a pending owner rotation | unfreeze; change settings; veto/freeze | attacker can *request* withdrawals to their own address, but ≥ threshold always queues under the model + RSC, instant flow is capped at 0.008 ETH per fixed one-hour window (a burst straddling a window boundary can reach up to twice that), and 11 requests inside one window freeze everything. The recovery key can rotate the owner (below) and tighten settings meanwhile. |
| verdictWriter | post verdicts to the registry | move funds; unfreeze; reconfigure | worst case is a freeze DoS (posted HIGHs freeze the vaults). Funds stay put. Recovery: registry owner calls `setVerdictWriter` with a fresh key, recovery key unfreezes the three vaults — 4 transactions, documented in `docs/DECISIONS.md`. |
| recovery (offline in production; on the operator machine in this demo) | unfreeze; change wait / threshold / instant cap; cancel any queued withdrawal; propose an owner rotation (48 h delay, owner can cancel, anyone can finalize after the delay) | request withdrawals; move funds; post verdicts | attacker could unfreeze and weaken settings, removing the safety margins — but moving funds still needs the owner key, and the model + RSC keep watching. The recovery address itself is set at deployment and cannot be rotated in place; a compromised recovery key means redeploying the vaults. A merely *lost* owner key no longer strands funds: the recovery key proposes a replacement owner and the rotation finalizes after 48 h unless the (compromised) owner cancels it. |

Disclosure: because MEDIUM×2 escalates, a leaked verdictWriter — or
just a burst of borderline traffic — can freeze all three vaults
cheaply (this happened unintentionally during the evidence run
above, when two Sepolia MEDIUMs landed within the hour). That is
deliberate: freezing is the safe direction, it is always
recoverable by the recovery key, and the alternative (a freeze
that needs a human to approve) would not land in time.

## Known limitations (second adversarial review, 2026-11-18 — updated)

The second review's contract-level findings (unwatched-verdict
trust, no per-request cancel, non-idempotent pace counting) were
fixed in the v5/v6 stack above and demonstrated live. What remains
documented rather than patched:

- **Verdicts are final.** The registry accepts exactly one verdict
  per request; a wrong score cannot be amended, only acted around
  (recovery unfreeze; the veto itself is permanent for that
  request).
- **Owner rotation does not defeat a compromised owner.** Recovery
  can propose a new owner, but the current owner can cancel any
  proposal — rotation is a lost-key remedy, not a compromise
  remedy. A compromised owner is bounded by the queue, the cap,
  the model and the pace guard, not by rotation.
- **Feature history counts requests, not executions.** A vetoed or
  cancelled request still makes its destination "seen" for later
  feature computation, because `first_seen` is defined over past
  requests. This is a modelling choice, disclosed here; replay
  reproduces it exactly.
- **Worker delivery depends on the worker process being alive.**
  Posting failures inside a run are retried (the scan cursor never
  advances past an unposted verdict, and a verdict counts only when
  its receipt confirms), but if the process itself dies, verdicts
  wait until it is restarted; it then resumes from the scan
  position and history it persists after every processed chunk
  (worker/worker-state.json; a first start rescans from the
  deployment blocks), and the registry's duplicate rejection makes
  restarts safe.
  The supervisor is not in this repo, but the process is not left
  unwatched: a watchdog on the operator's infrastructure checks it
  about every 30 minutes and restarts it via `scripts/wmanage.py`
  (in this repo), verifying the startup line from the worker log;
  worst-case downtime is roughly one patrol interval, and the
  fail-open design plus the RSC's pace guard bound the damage in
  the meantime.

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
risks stated) is in [`eval/RESULTS.md`](eval/RESULTS.md); its closing
section records the pre-registered adoption criteria for v3 —
including the one criterion v3 failed and the reasoning recorded
for adopting it anyway. One honest caveat about that comparison: a
hand-tuned rule with a 24 h cap would catch this known scenario
too; the model's advantage is that one code path adapts to each
vault's normal without per-vault tuning.

**Why a small model, not an LLM.** The verdicts are deterministic:
anyone can recompute a verdict from chain data with
`scripts/replay.py` and check it field-for-field, which an LLM's
sampling cannot offer. Inference is milliseconds on CPU only — no
API key, no external dependency, nothing to rate-limit or go down
between a request and its verdict. And there is no
prompt-injection surface: the model consumes numeric features
computed from chain events, never text an attacker controls, so a
crafted withdrawal cannot talk its way past the judge.

**Where an LLM does fit: explaining, not deciding.** Every verdict
is accompanied by a short plain-language rationale written by an
LLM that reads only the numeric feature vector and the verdict
record — never text an attacker controls — and writes after the
verdict is already posted, so it cannot influence, delay, or block
enforcement; if it is unavailable, verdicts continue without it.
The rationales live in `worker/rationales.jsonl` next to the exact
numbers they describe, so the words can be checked against the
features (design and a sample: `docs/verdict-rationales.md`). In a
production deployment this step is a hosted LLM API call in the
same slot; during this buildathon it is performed by the
operator's scheduled AI agent run, disclosed as such.

`modelHash = 0x0dfa7cb105d6c64d39889abc4926fc514b0cccf075c9e3071ddff893fcfd45c5`

The known-destination list the worker scores against is committed at
`worker/known_destinations.json` — replay from a clean clone uses the
same list, so verdicts reproduce exactly.

## Status during judging

Last verified on-chain: **2026-11-18** — all three vaults unfrozen,
balances and settings as in the table above, RSC reserves 1.0200
lREACT. The worker is a single process and is kept running until the
buildathon results are announced. A watchdog on the operator's
infrastructure checks it about every 30 minutes and, if it has died,
restarts it with `scripts/wmanage.py` (in this repo) and verifies
the startup line in the worker log before standing down; the
watchdog itself runs outside this repo, so worst-case downtime is
roughly one patrol interval (~30 minutes). Verdicts for any request
the worker missed are posted when it restarts (the registry rejects
duplicates, so restarts are safe). Liveness is checkable from
outside: the [VerdictRegistry event history on Base
Sepolia](https://sepolia.basescan.org/address/0x0e55C8F84F44336b766Af8469b74d5163abB7F32)
lists every verdict ever posted — the timestamp of the latest
verdict shows the worker is live. If the worker is down at any
point, the system fails open for queued withdrawals and the RSC
pace guard still applies — both behaviours are demonstrated in the
Proof section.

## Run it

```bash
forge test                                   # 45 unit tests
.venv/bin/python model/train_v3.py           # regenerate model.json + hash
.venv/bin/python eval/run_eval.py            # regenerate eval/RESULTS.md
.venv/bin/python worker/worker.py            # live verdict worker
.venv/bin/python scripts/replay.py --chain 84532 --request-id 3
.venv/bin/python scripts/print_config.py     # live config table from chain
```

Note: a single replay run can take several minutes — it scans the
origin chain's event history in small chunks (Base Sepolia limits
log queries to ~200 blocks per call).

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
  dropped. All findings were fixed (v4/v5), re-tested (38 tests at v4/v5; 45 now) and
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
