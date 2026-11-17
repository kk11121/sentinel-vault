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
