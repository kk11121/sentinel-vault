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

## M1 COMPLETE (2026-11-17) — final stack
Root cause of the dead loop: REACTIVE_IGNORE. The docs name the wildcard but
never print its value. 0xFFFF...FF is recorded by the system contract yet never
matches in validator delivery. The value every delivered subscription uses is
0xa65f96fc951c35ead38878e0f0b7a3c744a6f5ccc1476b313353ce31712313ad (found by
byte-comparing live subscription events). Fixed in OmniReactive.sol; a Lasna-
local Ping test then fired react() within ~55 s.

- SentinelReactive v2 — Lasna: 0xCdbB1ca6008Fc57Bf10C0f4e4e600b987f6AAFfD
  deploy tx 0xa61533835076de370eef62bad3056aabba0dc0cfc2aeb2f850febdff2d22fce1 (1.5 lREACT balance + 1.0 reserves)
  setVault tx 0xa3fc447159a4d92315e7e64b69f93dae4a0f221d189fc52ca34932c4a9b88565
- GuardedVault v2 — Ethereum Sepolia: 0xF07bC9b4A3418A9B54aD8145C4cBe2f268BFD55A
  deploy tx 0xe7a404b1e50b5bc22a531452d5a1746fc11b5ceb63d00af3ac486b854be96654 (0.01 ETH + 0.005 proxy reserves)
- Acceptance run:
  1. verdict #5 HIGH (Base) tx 0xdb7859e62dcfb39886b8379ee8717be8597fcb2e48ca08e8c6da8fb2ff194ce3 — Success
  2. Frozen delivered on Sepolia: tx 0xd2e557978361c86538974c279650b8af5272e7dbba2c9245ab9e7ef2316072d4 — frozen()==true ~50 s after the verdict
  3. Negative test on the final vault (attacker direct freeze): tx 0x29d7d0639cc3c018570f4f6b5794ef0732ef22cffffa04b63c6d143458305ae8 — FAILED as expected
- Old v1 contracts (RSC 0x68A10a..., vault 0x14B661...) are superseded; their
  subscriptions used the broken wildcard and will never fire.

## M2 stack (2026-11-17)
- SentinelReactive v3 — Lasna: 0x946181Feb969e29cA42aF5dB0b17325CA524262e
  deploy tx 0x6a625051b6bab8d60601a254ebba60e0ed6d039196a91c8e0d724af6d5ff2451 (1.5 balance + 1.0 reserves, depositTo tx 0x754c9c2f...)
  setVault done for 84532 / 11155111 / 1301.
- GuardedVault v2 (wait 180 s, threshold 0.02 ETH, funded 0.01 ETH + 0.003 proxy reserves each):
  - Base Sepolia: 0xFf25f82b50c0164D815D0d18037afab502D2b926 (deploy 0xc954e084...)
  - Ethereum Sepolia: 0x95Fd0764a2f75387F35c8eEAB409aa1410b19b2d (deploy 0x089f04fe...)
  - Unichain Sepolia: 0x68A10a67C79593d6e4a69AB7Abc5762380Dc5560 (deploy 0xf95daa79...)
  (Cross-chain address coincidences with Lasna contracts are deployer-nonce artifacts, harmless.)
- Faucet conversions so far: 3 x 0.05 Sepolia ETH -> ~15.75 lREACT total. Watch the
  deployer Lasna balance during heavy test cycles; it drains fast.

## M2 LIVE VERIFICATION (2026-11-17) — all cases PASS on the M2 stack
Worker: worker/worker.py rule-v1 (dummy rule; verdictWriter key; verdict for
every request). Note: worker lookback is 2000 blocks at startup — Base Sepolia
advances ~2000 blocks in ~35 min, so stale requests fall out of the window;
the worker is a live watcher, not a catch-up indexer. (A long detour blaming
the Base RPC log index was actually an arithmetic slip: 0x392d7db = 59955163.)

- Case A (normal, fail-open): Base vault req 3, 0.006 ETH to owner (known)
  request tx 0x12042758c20a2576a522c3a407a4a8c314f068ba20ad1d06dd08f17476fd723e
  LOW verdict tx 0xb293d32564523c6934634b414bfd00c08a9811de105bce45b91cf0c7ae267794
  executed after wait, tx 0x85f28dcff94609345aa0320f1ae4ba4a25a5a1d16f548973d08a3b8dec5a28ad
  (One earlier execute attempt failed silently at gas estimation — transient
  RPC issue suspected, cause not pinned down; the retry succeeded.)
- Case B (veto): Base vault req 4, 0.006 ETH to first-seen attacker address
  request tx 0xfe1728e39a9ec4f705b31a3a7eeb83edd461c1e5f35c8408abb9c6fc1a47e3b0
  MEDIUM verdict tx 0x015b91617be393bb0fee65c4d7b8654712cb568ac9129718922026c8f841f3a5
  -> withdrawals(4).vetoed == true via RSC callback; execute reverts Vetoed.
- Case C (escalation): Base vault req 5, 0.006 ETH to fresh 0x...dEaD
  request tx 0xcddd23b45eeb463476be32c75d39b10737b79e052a10a46535ffc524e1ce755a
  MEDIUM verdict tx 0x10ee24497ed134e82b556b4811b30e37a2d4e81830eda8fd1724ec6508688377
  -> second MEDIUM within the window escalated: frozen()==true verified on
     Base, Ethereum Sepolia AND Unichain Sepolia vaults. Cleanup: owner
     unfreeze x3, all Success.

## M3 MODEL LIVE (2026-11-17)
- Model: Isolation Forest exported to model/model.json (139 KB, no pickle),
  modelHash 0xc65a9db604e61be432fe2822e9cbcdfd97f75698593372377b1987dc5b5f6bb7,
  thresholds MEDIUM>=598 / HIGH>=655. Pure-python scorer parity vs sklearn:
  Spearman -0.9999 on held-out data.
- Worker v2 (model) posted a HIGH verdict for the stale Base req 5 on its
  startup rescan (tx 0x08b7a368...) — RSC froze all vaults; owner unfroze x3.
  (Worker restart re-judges requests still inside its 2000-block lookback;
  handled-set is in-memory. Noted for the demo runbook.)
- M3 acceptance run: Sepolia vault req 1 (0.004 ETH to owner,
  tx 0x47f65beb7a14aa3b4e863666740c2d5043b5d6b2af6e53126f5c253d5325b4e0)
  -> model verdict MEDIUM 603 (tx 0xbe2be1969291db2187c55d7d20ddb9a7d41717a15b05c6b5aeee75a51eabef77)
  -> vetoed on-chain via RSC. balance_ratio 0.4 (tiny demo balance) drove
  the score — documented in MODEL_CARD limitations.
- Replay verified: scripts/replay.py --chain 11155111 --request-id 1
  -> severity/score/featuresHash/modelHash all MATCH.
- Eval (eval/RESULTS.md): model flags more normal traffic than the rule
  (3.8% vs 0.8%) and false-HIGHs a 3x-median legit transfer, but is the
  only method that escalates a small-amount barrage to HIGH. Published as-is.

## DEMO RUN (2026-11-17, filmed for the submission video)
Base vault topped up to 0.020 ETH; wait set to 60 s for filming (restored
to 180 s afterwards). Worker restarted just before: its Base history was
empty (req 5 outside the lookback), but its Sepolia req-1 re-judgment
posted a 2nd MEDIUM within the on-chain escalation window and froze all
vaults once — owner unfroze x3 before filming. LESSON: the RSC's
lastMediumAt persists on-chain; a worker restart inside the window is
NOT a clean slate. Wait out the window or expect one escalation.
- Normal: Base req 6, 0.008 ETH to owner
  request 0xa71fab2b85115a32e79e028a901b3012f754e123fb62b631bd37f9774cf3d088
  model LOW 562, verdict 0xbc136b1599839e511481405f64a8a8ccf2b34700b0182d831e0f2e10e93aa6ba
  executed 0x627e22b570ae0df4c4f0ba4cf0cdd589e2d0c2dc918d8f1907875919f0303609
- Attack: Base req 7, 0.008 ETH to first-seen attacker address
  request 0x86cc98e93af0e2a642c5a888033147a9cdaf59538a1322b83f3debaeb605d72f
  model HIGH 728, verdict 0x760a60568090c4f84568c2dd8d315e9170d6ebda73a3bb877756d25163ec699e
  -> all 3 vaults frozen (verified); execute(7) reverts VaultFrozen.
  Replay of the verdict: severity/score/featuresHash/modelHash all MATCH.
- Post-run: unfreeze x3, wait restored to 180 s.
