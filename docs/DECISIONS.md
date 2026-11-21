# Decisions log
- 2026-11-17 | Build A' Sentinel Vault per Claude's instruction document | User confirmed A' and the three embedded decisions via options widget.
- 2026-11-17 | Owner decisions approved: (1) up to JPY 3,000 spend if free faucets have not delivered by 2026-11-19, (2) owner time for this project capped at 1.5 h/week (inside the 5 h/week total), (3) proceed in parallel despite eligibility being unconfirmed; stop immediately if the organizer confirms Japan is out.
- 2026-11-17 | Build on the Omni API, not legacy RVM style | Lasna migrated to Omni (RVM removed); legacy remains supported but new work should target the current architecture.
- 2026-11-17 | Project repo lives at ~/workspace/sentinel-vault (to be published as a public GitHub repo at submission) | Keeps build artifacts separate from goal bookkeeping.
- 2026-11-17: REACTIVE_IGNORE = 0xa65f96fc...13ad (empirical, from live subscription events). The all-FF guess cost ~2 hours of M1 debugging; any future Reactive contract must use this value and the Ping test must pass before real deployments.
- 2026-11-17: Always verify reserves() after every depositTo; one early depositTo did not credit (cause unknown) and silent assumption wasted a test cycle.
- 2026-11-18: Claude pre-submission review received; its top findings verified TRUE against the code (S1 requestWithdrawal had no auth check — anyone could withdraw; S2 no instant cap; S3 owner key could unfreeze/reconfigure instantly). Fixes adopted from the review's A/B lists and implemented the same day: owner-only requestWithdrawal, per-window instant cap with overflow routed to the queue, recovery key split (unfreeze/setWait/setThreshold/setInstantCap are recovery-only), VerdictRegistry takes chainId and rejects duplicate verdicts, RSC v4 watches WithdrawalRequested on all vaults (known-request check for MEDIUM vetoes; HIGH freezes regardless but is flagged UnverifiedVerdict) and freezes all vaults on its own when cross-chain request pace exceeds 10/hour, veto/freeze made idempotent. 23 unit tests pass. Recovery key is a fresh testnet key in .env (RECOVERY_*), generated without ever being printed.
- 2026-11-18: Model v2/v3 built per the Claude review (B2 + A6). v2 = generator-v2 data (rare large-to-known payments) + calibration-set thresholds: false HIGHs on held-out normals 6/236 -> 0. Evaluation then exposed a total blind spot in ALL 6-feature methods (rule included): a slow drain to an already-known address at 10-min pace scored LOW on all 20 steps (1h pace features plateau). v3 adds 24h pace features (f7/f8): flags the drain at step 2, zero false HIGHs on every held-out set incl. monthly-large, both rare-legit probes LOW. v3 fails one pre-fixed adoption criterion (concentration flagged at #2 vs v2's #1); adopted anyway with the override and reasoning recorded in eval/RESULTS.md rather than editing the criterion. Deployed model.json = v3, modelHash 0x0dfa7cb1...; v1/v2 files kept in repo.

## Key-compromise procedures (adopted 2026-11-18)
- verdictWriter leaked: registry owner calls setVerdictWriter(fresh key);
  recovery key unfreezes the three vaults. 4 transactions total. Funds
  stay frozen (safe) until the unfreezes land; the leaked key's worst
  case is a freeze DoS, never a transfer.
- Owner (daily) key leaked: recovery key tightens settings (instant
  cap to 0, longer wait) to slow requests; rotate the owner by
  redeploying or migrating funds to a fresh vault; queued requests to
  attacker addresses are vetoed/frozen by the model + RSC meanwhile.
- Recovery key leaked: no in-place rotation (address is fixed at
  deployment). Treat as a redeploy event: deploy fresh vaults with a
  new recovery key and migrate balances.

## 2026-11-18 — Full audit (owner-ordered re-verification)
- Independent contract review + self re-verification. Tests 23/23, eval
  re-run byte-identical, modelHash re-derived and matching on-chain.
- Fixed: worker and replay now rebuild history from the deployment
  blocks recorded in deployments.json (the old bounded lookbacks could
  skew the 24h features after a restart); replay orders same-block
  requests by logIndex and retries transient RPC errors; generated
  video intermediates and worker.log untracked from git.
- Open findings F1/F2 (HIGH): a HIGH verdict freezes but never vetoes
  its own originating request, and a MEDIUM verdict delivered before
  its WithdrawalRequested is dropped permanently. Fix = RSC v5
  (veto-on-HIGH + pending-veto buffer + chain-aware keys + dynamic
  freeze list), pending the owner's go-ahead.

## 2026-11-18 — Audit fix programme executed (owner ordered "fix everything")
- All findings F1-F13 fixed: GuardedVault v4 (aggregate pending
  reservation, zero-amount / invalid-destination / zero-address
  validation, owner rotation proposed by recovery with a 48 h delay
  and owner cancel, setInstantCap resets the window) and
  SentinelReactive v5 (HIGH and escalation now veto their own request
  before freezing; MEDIUM/HIGH verdicts delivered before their request
  are buffered as pending vetoes and applied on arrival instead of
  being dropped; escalation state keyed per (chainId, vault); freeze
  list built dynamically from watched chains; watchVault idempotent).
  Base contracts: dead _coverDebt removed; pay() trust assumption
  documented in code and README. Tests 23 -> 38, all passing.
- Redeployed as the v4/v5 stack (see docs/deployments.md). The
  VerdictRegistry was kept (redeploying it would have invalidated all
  historical verdict evidence); its source is unchanged so the repo
  source still matches the deployed bytecode. Old v3 vaults were
  drained back to the deployer through their own withdrawal flow.
- Evidence re-run on the new stack, including the F1 proof: after a
  recovery unfreeze, executing the HIGH-flagged request reverts
  (Vetoed) - under the old RSC it would have paid out.
- Noted during the run: Ethereum Sepolia meters the vault's
  requestWithdrawal at ~710k gas via the public RPC (identical
  bytecode ~150k on Base) - a chain/RPC artifact; evidence scripts
  budget 1.2M gas there. Also: worker.log is append-only across
  stacks, so log greps must be cross-checked against chain data
  (an old-stack line briefly suggested a duplicate verdict for the
  new stack's request 5; chain data proved the verdict unique and
  correct - HIGH 684 from the burst history).

## 2026-11-18 — Second adversarial review; worker H1 fixed, contract items disclosed
- An independent subagent re-audited the post-audit stack: no Critical,
  no regression in F1-F13. New findings: H1 (worker could silently
  drop a verdict until restart), M1 (RSC does not check a verdict's
  (chainId, vault) against the watched table), M2/M3 (no per-request
  cancel; unexecutable requests lock their reservation), M5 (vetoed
  requests still enter feature history), M6 (pace counting not
  idempotent), plus documentation errors.
- Owner's decision: fix H1 only; disclose the contract-level items
  in the README instead of a v6 redeploy (a redeploy would orphan
  the evidence set and the deployer is out of testnet funds).
- H1 fix in worker/worker.py: verdict payloads are prepared exactly
  once per request (feature order preserved), posting is confirmed
  by receipt, the per-chain cursor advances only past posted
  verdicts, failures retry head-of-line on later cycles, and every
  per-log exception is contained so one chain's RPC failure (429s
  observed live on Unichain) can neither kill the process nor stall
  the other chains. Verified live: Base request 14 judged HIGH 691
  by the fixed worker, vetoed, all vaults frozen, then unfrozen.
- Documentation errors found by the review (broken HIGH-verdict
  link, instant-cap count, a packet reference to a non-existent tx)
  were fixed the same day.
- 2026-11-18 (night): The owner reversed the fix-H1-only decision after
  personally restoring testnet funding (a full pk910 PoW faucet session,
  +2.5 Sepolia ETH) and ordered the v6 programme: RSC watched-verdict
  check (M1), pace-count idempotency (M6), and a per-request
  cancelWithdrawal (M2/M3 mitigation) in the vault, followed by a full
  stack redeploy, evidence re-run, video re-render, and re-verification.
  Forge suite extended to 45 tests (7 new), all passing before deploy.

## 2026-11-21 — Post-submission Claude review; fix programme executed
- Claude's post-submission adversarial review received (2026-11-21):
  predicted score 16-17/20 (Execution 5, Integration 4, Usefulness
  3-4, Craft 4). Headline finding: the substance is sound; the
  weakest point is evidence presentation (dead explorer links,
  cross-chain freeze not traceable from the README).
- Muse verified every point against the code, the repo and the
  chains before acting. Adopted and fixed the same day:
  - C1 (headline overstated the first-withdrawal freeze): README
    headline rewritten to the measured behaviour (first anomalous
    withdrawal vetoed; by the second, all vaults frozen).
  - C2 ("per hour" caps are fixed-window): all plain per-hour
    phrasings in the README qualified as fixed one-hour windows
    (boundary straddle can reach up to twice the cap). No contract
    change — a redeploy would orphan the evidence set.
  - C3 (cross-chain freeze evidence incomplete): the four dead
    explorer links fixed (sepolia.etherscan.org -> .io,
    sepolia.unichain.org -> sepolia.uniscan.xyz), and the freeze
    callback txs for the HIGH-735 and MEDIUM-escalation episodes
    recovered from the destination chains' logs, verified, and
    added to the README Proof section and docs/deployments.md.
  - C4 (worker-liveness text stale): README "Status during
    judging" and the Known-limitations worker bullet rewritten to
    the real setup (watchdog on operator infrastructure, ~30 min
    patrol, restarts via scripts/wmanage.py, runs until results
    are announced) plus a VerdictRegistry event-history link so
    liveness is checkable from outside.
  - C5 (slow-drain claim overgeneralised to all fixed rules):
    clarifying sentence added to the README and eval/RESULTS.md
    (a hand-tuned rule with a 24 h cap would catch the known
    scenario too; the model's advantage is per-vault adaptation
    without tuning). Video/narration NOT edited, by decision.
  - C7 (README said both 45 and 38 tests): the historical mention
    now reads "38 tests at v4/v5; 45 now".
  - R2 (recovery key described as "kept offline" while the demo
    key sits on the operator machine): README now splits the
    production design from the testnet demo reality.
  - Craft cleanup: PingTest.sol/PingTest2.sol and the superseded
    video builders + frame sets moved to archive/; video/README.txt
    rewritten for the shipped v7 video; forge suite still 45/45.
  - Unichain vault topped up by 0.002 ETH (tx in
    docs/deployments.md) so it can keep paying callback fees.
- Deferred:
  - C6 ("Last verified on-chain" date + config table refresh):
    scheduled as a single final pass on 2026-12-05, just before
    the deadline, so the date judges see is days old, not weeks.
- Process rules adopted from the review:
  - R1: ALL repo and BUIDL changes land before the submission
    deadline (2026-12-06 05:00 JST); no commits after it, so
    nothing can look like out-of-period work.
  - R3: balances (Lasna reserves, verdictWriter gas, vault fee
    balances) are planned to last up to ~2 months of judging.
  - R8: the worker watchdog also checks the vaults' frozen state
    and reports an unexpected freeze.
- Heartbeat adopted with safeguards: a daily 0.001 ETH withdrawal
  on Base to the owner (known destination), judged and executed,
  then re-deposited, so the latest-verdict timestamp stays fresh
  through judging. Pre-scored locally with the repo model before
  starting: at a steady 24 h cadence the score is a stable 553
  (LOW, margin +67 to the MEDIUM threshold 620) with no drift over
  14 simulated days — BUT any gap of >= 48 h saturates the
  interval feature and the next request scores 632 (MEDIUM, veto
  only). The current gap is already ~61 h, so the first heartbeat
  must be treated as a sacrificial primer: expect a veto, never
  re-request within the same hour (a second MEDIUM inside 1 h
  would escalate to a freeze-all), and start the daily cadence
  the next day. Stop the heartbeat immediately if any verdict is
  MEDIUM or worse beyond that planned primer.
- REJECTED: R5 — posting the Japan-eligibility question to the
  Reactive official community / Telegram. The user declined this
  for the second time (first on 2026-11-17); the DoraHacks Q&A
  question of 2026-11-17 stands as the only inquiry.
- NOT done, per the review's own "do not" list: no contract
  changes (no sliding-window rewrite), no model swap to an LLM,
  no video re-shoot, no YouTube re-host of the demo video.
- 2026-11-21 (later): worker scan fix. The original poll loop
  fetched the whole cursor-to-head range in one all-or-nothing
  pass; after a restart the Base Sepolia backlog is ~1.1M blocks
  (tens of thousands of getLogs calls), so a single failed chunk
  discarded the entire pass and a restarted worker could never
  catch up — in practice no new request had been judged since
  the 2026-11-18 evidence run. The loop now fetches and
  processes bounded slices, advances the cursor chunk by chunk,
  and persists cursor + rebuilt history to
  worker/worker-state.json (gitignored) after every chunk, so
  restarts resume where the previous process stopped. H1
  delivery semantics unchanged (the cursor never advances past
  an unposted verdict; feature order preserved). Live proof the
  same day: the worker caught up past the full backlog, judged
  Base req 12 (the heartbeat primer, below), and a watchdog
  restart resumed from the persisted state instead of rescanning.
- 2026-11-21: heartbeat primer fired as planned — Base req 12,
  0.001 ETH to the owner (request tx e50ca563687be95b74d1b735d-
  e176676f9eba1747f28df6ae26684d0ffcfe5dd). The worker scored it
  MEDIUM 632, exactly the pre-score prediction (the interval
  feature saturated after the ~61 h gap); the RSC vetoed it
  (verdict tx 0b9caf6524576d0071c0f8d70ea3865d96f618fd911e4553-
  ba5907a744a45cc7), no vault froze, funds untouched. The daily
  heartbeat cron is live with the recorded safeguards:
  pre-score before every submission, predicted HIGH = never
  submit, unexpected MEDIUM-or-worse in steady state = stop,
  primer days submit once and never twice within an hour.
- 2026-11-21: BUIDL description updated via Manage Submission.
  Read-back of the live form showed the C1 overclaim and the
  unqualified cap phrasings existed only in the README, never in
  the BUIDL text (its description starts at "Why this design"),
  so the only change made was appending the "Live during
  judging" paragraph (watchdog supervision, the daily heartbeat
  verdicts, the VerdictRegistry liveness link, the ~17 s
  worst-case freeze figure) at the end of the description.
  Saved and verified on the public page; nothing else in the
  submission was touched.
- 2026-11-21 (evening): LLM explainer added — a scoped exception
  to the review's "no LLM" do-not, which targeted a model SWAP.
  The Isolation Forest still decides every verdict; an LLM now
  writes a plain-language rationale for each verdict after it is
  posted, reading only the numeric feature vector and the
  verdict record (docs/verdict-rationales.md). It cannot
  influence, delay, or block enforcement, and verdict
  reproducibility, thresholds, and the eval accounting are
  unchanged. During judging the step is performed by the
  operator's scheduled AI agent run (appended to the daily
  heartbeat); the production mapping (a hosted LLM API call in
  the same slot) is documented in the repo. Rationales are
  stored in worker/rationales.jsonl beside the numbers they
  describe, starting with the req 12 primer verdict.
- 2026-11-21 (later): explainer hardened per the owner's chosen
  package. (1) Faithfulness: features must be cited as
  name+value, and scripts/check_rationale.py mechanically traces
  every number in a rationale to its record (declared
  derivations in allowed_extra) before the rationale is kept;
  verified PASS on the primer entry and FAIL on a corrupted
  copy. (2) Observations: the explainer also files a note from
  outside the feature vector (other chains' recent requests and
  frozen state, hour of day, destination's cross-chain
  footprint), advisory only, stating the limits of its own
  read. The live model itself stays frozen — new features
  would change modelHash and break the submitted coherence;
  detection-scope work is deferred to a post-results v2.
