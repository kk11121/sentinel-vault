# Deployments (M1, 2026-11-17)

- VerdictRegistry — Base Sepolia (84532): 0xEe60c9776CAc32bda21ED7e6cAD1497717B28A12
  deploy tx 0xb6bfa89e2937ce9537f8ec23ceea9a100366ea1590053eabf308ec9f9f5158fa
- SentinelReactive (RSC) — Lasna (5318007): 0x68A10a67C79593d6e4a69AB7Abc5762380Dc5560
  deploy tx 0x40f48ff04abc64ea5f1f6ff7bbd2fb0b21622f992b9da844fe9de5ff15e234be (funded 2 lREACT)
  Subscription confirmed in the deploy receipt: system-contract log records chainId 84532,
  registry address, VerdictPosted topic0, REACTIVE_IGNORE x3.
  setVault(11155111, vault) tx 0xdc2f20e64341f0ef78a0ef42c96cf1bfae5e0a5926ba7a524ede5a853004cbe9
- GuardedVault — Ethereum Sepolia (11155111): 0x14B6610414E14F77ACeDB72D6aCb13edadbf0D7B
  deploy tx 0x3ee8ddf979c3f1af611c66c8e525f3074ff5c5aa199b63f2ef69455ffd63a3a1 (funded 0.01 ETH)
  callback proxy 0xAa14d9Cd0f788Ca23d11805986C1d8bd035D23b4, callback sender = RSC.

M1 loop test:
- HIGH verdict posted by verdictWriter on Base: tx 0xe111a69854fceed16bd08fb087e2c693e2965710bab9215ea06193a9b4c23b02 (Success)
- Negative test: attacker EOA called freeze() directly on the Sepolia vault:
  tx 0xde60764557b5f94495d8c1baae61a9152a37489d8679d0a710b0361796fc20a4 — status FAILED as expected.
- Reactive reaction + callback freeze: PENDING as of 18:35 JST (waiting on origin-chain
  indexing/finality on Reactive's side; subscription, topic0, funding, and zero debt all verified).

## Reaction troubleshooting log (2026-11-17 evening)
- Verdicts #2 (0xaf56e32d...), #3 (0x1b633f80...), #4 (0xc7dc864d...) also posted; no reaction yet.
- Verified NOT the cause: subscription event registered on-chain (deploy receipts, correct
  chainId/contract/topic0/REACTIVE_IGNORE format — byte-compared with working subscriptions);
  topic0 matches the registry event; RSC balance 2 lREACT, reserves topped up via
  SYSTEM.depositTo (RSC 1.0 lREACT), debt 0; network is live (28 trigger txs / 16 distinct
  RSCs in the last ~5000 Lasna blocks, incl. Base Sepolia origins).
- Isolation tests: PingReactive (constructor subscribe, Lasna-local Ping) and PingReactive2
  (0x95Fd0764a2f75387F35c8eEAB409aa1410b19b2d; post-deploy arm() subscribe, reserves 0.3)
  also show no react() invocation and no charges — delivery to NEW subscriptions appears
  not to start immediately. Working hypothesis: validator-side subscription sync latency
  with no backfill; events fired before sync are lost. A background watcher is polling
  frozen()/count for ~30 min after verdict #4.
- Note: first depositTo for PingReactive2 did not credit reserves (cause unclear);
  a second depositTo (0.3 lREACT, tx 0xce6f5337...) credited correctly. Always verify
  reserves after depositTo.
