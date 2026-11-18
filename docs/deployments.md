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

## v3 stack (post-review redeploy, 2026-11-18) — SUPERSEDED by v4/v5 below (vaults drained 2026-11-18)
Review fixes deployed: owner-only requests, instant cap, recovery key,
registry v2 (chainId + duplicate rejection), RSC v4 (request watching +
pace freeze). Config on all vaults: wait 180 s, threshold 0.004 ETH,
instant cap 0.008 ETH / 3600 s.
- VerdictRegistry v2 — Base Sepolia: 0x0e55C8F84F44336b766Af8469b74d5163abB7F32
  deploy tx 0x3556dc5fdcaaae3db85681303d6c196fc4727e8573b2fefdd703bdae6f789682
- SentinelReactive v4 — Lasna: 0xeaE20eccD1F308CaB3e8a4c99e588D8CC21a1ff8
  deploy tx 0x794d047dd3c3648c1979d28c6c79a8ea144c1e007c728309f42d3272ebe3d662
  (1.5 lREACT balance; reserves 1.0 lREACT via depositTo tx
  0x98e8baa887c8772c0351091449a10d06f8b7b568ead09453be2ec85e4f9eb859, verified)
- GuardedVault v3 — Ethereum Sepolia: 0x0C0c54778431652a2c6b92E088fB02335d395BED
  deploy tx 0x3820dc08247481abf11dd5209114671c058ee43d52e5816e31c3d2936194e4ec (funded 0.008 ETH)
- GuardedVault v3 — Unichain Sepolia: 0x95Fd0764a2f75387F35c8eEAB409aa1410b19b2d
  deploy tx 0xedd3458c9bc19281fdef5079e4816ebc3f2a5b7b3dd7ff401c017046551cfaae (funded 0.012 ETH)
- watchVault txs (Lasna): Sepolia 0x43f8ce7b7be601f0ee63589040979573f4fef004acab3e33d1ae4bfbd9c2093c,
  Unichain 0x46016a8c3bd10679fba2433510faec0078eb4542fbda3ea4c5addd2b23c00a4d
- Recovery key funded 0.0015 ETH on each chain (Sepolia tx
  0x01ebaad311ca2c72a52549339fa49f440e5fd3a5f8562970105ab9e8fbbcdc50, Unichain
  0x695178b22501706d31c5d297cc50e9e83f63ed5758a99e41cb5cd4964eef6dda, Base
  0xcc26fe926d3837463a8b8532a7e244d72bf9d240a4602e069b3621030c6382de)
- Bridge 0.03 ETH Sepolia->Base for the Base vault funding: L1 tx
  0x943f812e92de73849a3e1b47f205534fb1908b219527261fe09bcfe93ba06944 (crediting pending)
- CORRECTION to the M2-era notes: the system contract address 0x8888...8888
  has NO code on the destination chains, so the "proxy reserves" depositTo
  calls there were plain transfers to that address. Destination callback
  fees are in fact paid from each vault's own balance via OmniCallback.pay()
  (the proxy calls pay(amount) on the recipient). Vault balances are what
  matter; the two 0.002 ETH transfers made today (Sepolia tx
  0xac86757d76a8d7b3395504b072e1bce2a38f881c630cdb3b251d45aacc0cd743, Unichain
  0x47519a8a35d3e63ba45e5ee9253f780c758c449835b7166a80b711a2ec7e2bca) repeat
  the old mistake and are documented here so nobody models on them.

### v3 scenario evidence (2026-11-18, model iforest-3, wait temporarily 60 s)

Base vault: 0xAf17d1e294c35cA4eFE35c58B201D6F95Aef3DE4 (deploy tx
0x8cc698dbe22b3ae13cb8ad3d2a842278a290647d7b379d7882266afefc282b4e; watchVault
tx 0x0fbdd7e06b02e550d25f5672ecfd3d4f60e2f13ef62b3965336dbc32fde1cb76).

Negative tests (both broadcast, both FAILED on-chain as designed):
- Attacker EOA requestWithdrawal (Base) -> NotOwner:
  0xf1d85a7b8bc8c30d99852d79f18bf1e9287631649b7bfb1ce83f2843512ebbfb
- Owner-key unfreeze attempt (Base) -> NotRecovery:
  0xe04e96ab3dd5199cc93c0dd7e7ee997ac262185588acffdf4c2bae754aec056c

Case A - normal queued withdrawal (Base, 0.008 ETH to owner):
- request: 0xeebd5b7e694dd1ecf234a31c69800cb4e6168a57264225fa39c24b77774978da
- Lasna reactive tx (RequestSeen): 0x4dfa549d1f658a2bd554ceb2e757b74dbefda8fa7b53cad379e2200fb942a3b7
- verdict LOW 583: 0xd9566a099b529eb0a4a781b161d9ca82a5e9536f56d18f97a623fc1a6d6d17b8
- Lasna reactive tx (VerdictIgnored): 0x41b8f05187b1f9a0dc13f3dde061be427ddd3ece51c7e568e9fe3d5a1fe1761c
- executed after the wait: 0x15edb14cc5393733e86372b61cde3f8c87d7d7650fac692040fe17576e2cb6be

Instant cap + burst escalation (Base, 3 x 0.003 ETH to owner, seconds apart):
- requests 2/3/4: 0xc57667295e00108bdcc6e759614a6bff654eb925f1658ae8ebd3c61e866f40a1,
  0xf6886b263b150ecefa78308927021b2d09f437b178ec1225bc17c8bb92b5a947,
  0x95c86a5130217b841f5f41e7ec19f2d17714f5e747c357b1a9df1b6caea00bdc
- readyAt proof of the cap: req 2 and 3 were instant (readyAt = request
  time); req 4 was queued by the cap (readyAt = request time + 60 s).
- req 2 verdict MEDIUM 662: 0xc928d167388426fc77f437a4cd60fcaecfb54df74147984021b820d717d2e88a
  -> Lasna VetoRequested: 0x3058ab3d4474042e4ff045abfac5611be32290287c5faa705a990e9bda91a0b4
  -> veto callback (Base): 0xa5c2bc1c8c291860a9d7afe6e25714106d1bb81a086f225f12cbf7a4da4897a3
- req 3 verdict HIGH 713: 0xa0ee51c8d547a8d1630b7a2108005d9c2595d4b48070e2d99192126bc9f559bc
  -> Lasna FreezeRequested x3: 0x2e4156422a237d9234fd0eeb2b902ea2484aacb429f86e9e66da42dbcac98027
  -> freeze callbacks: Base 0xce4bd4742251bebd2e616c6a846abb6416d419d4af3f6b350f8a5b7d4bf2acb4,
     Unichain 0x1f3600be20a360e8792d6775b78ffb9baac9ad56a6bf5b89076928c2e3d28d35,
     Sepolia 0x68a8b1b2f129eae8ace86a9eaaeb93b322394e74298a8365745a595fca9ba090
- req 4 verdict HIGH 717: 0x1f544c320175ab9edee5a1a32da9f8c42ec1bb7d48ec8533d218a47005244a58
  -> Lasna FreezeRequested x3 (idempotent, no revert):
     0x33c76ecbb8c75262f00b2d25b8b2b57ebb04a87c570e1b2cbfeb650061124d03
- recovery unfreeze x3: Base 0x87cd9589caf3d6583c16fdaec8eced6ad2d01fe26f78c0080726a1b08fd8df30,
  Sepolia 0xa7ebff10b530056ac38993156c7885273b4ad4d0edcf88fa2454c208c1f8e0f7,
  Unichain 0xf985fd854b987630e9f7e8886536d6e9400871d40763d7994fc5e8e3b392eed2

Pace guard (RSC alone; worker deliberately stopped for the trigger):
- Six 0.001 ETH requests (Sepolia x3: 0xa1f829a12c7a37672fcddb6551c17122ff2997241d1c24f54113598a948d0df4,
  0x6e2b3bf1eb8b94176a5dbaf1ed3556758e2e3a016c1815c012fe84057af8e27c,
  0xbe61e80c00325358b9c1cf3a237710d8df9bd68dcd200656b889849a29b2b63e; Unichain x3:
  0x9bfe15e0352989da9b70a0fbf7c1d883c549d71cd07f55a856e6c5344b3b62f3,
  0xaeffa4b2fc9ce40d1ed1b5c18094e18a8e1276fc77e5d150141fa6248159d527,
  0xa9a607e716c73eb1add0d010061ceb51bb9f3cafa6e0a3a21201992fde08623d). Model verdicts
  during the run: Sepolia LOW 571 / MEDIUM 647 (req 2 vetoed on Sepolia:
  withdrawals(2).vetoed = true) / HIGH 696; Unichain LOW 522 / LOW 611 / HIGH 675.
  A 7th request then FAILED with VaultFrozen:
  0x072d04154749d14111b54afc369f2f776a04b9f8604d4ca725f7db06b74947d3
- recovery unfreeze x3: Base 0x91a5773393f4045e09d0f747a40e712c526db35976a996a29206eb5c918043ff,
  Sepolia 0xad2aa9be647fe644fb9141b5cc641f4a28420578f0ec2c0c9280a1a1a75a0629,
  Unichain 0x6b72bc1355aa5656b9928faae1259e27296ecc107d84e12f1920dc56d316b2ca
- 11th request inside the 1-hour window (Base req 5, worker stopped):
  0x0af58b70933a5ac581a27c69aa8f709ecb6aaad234095a6a7545b6a9a47aa2f1
- Lasna reactive tx (RequestSeen + PaceFreeze + FreezeRequested x3 in one tx):
  0xf5aeb1e9e1603adbc90b695e10241d1e540a25692cea8ebe0283621b0eaf0fbc
- pace freeze callbacks: Base 0x98bfb7b81bc7d90c776fd8cd21a9b5b9de1fc6524ea542765db67e69126814d7,
  Unichain 0xd6b22bc1d072217978c99d7e615b0fc69708966c10bcdb483d5c93ef2dff82ac,
  Sepolia 0xcce2cf3e2ccb90333d8c01a0d1ed007b86c5f5ebc9506709e8d5102c6721ab84
  (paceCount read back as 11, paceFrozen = true)
- recovery unfreeze x3: Base 0xe216a170772f6d727d279b2a5e9b6b80c1edc1cc5cfbf1e04a992adf119f8414,
  Sepolia 0xe658792c538dc765ef8f3bda456b468ed69ec72919d4dc8bdfe7f8d8895be14b,
  Unichain 0xd543ab3fe6f972c8a8b46f58ad3476d4a1f64c5964f741b97527b5d1ae8381f1
- worker restarted afterwards: Base req 5 judged LOW 522
  (0x9790688482ca9a73bfb8ec46056b5585cdc52b3f750c88ca1ac652d6b7b4441f); every
  earlier request was skipped via the registry hasVerdict check.

Replay verification (scripts/replay.py, recomputed from chain data):
- Base req 1: severity/score/featuresHash/modelHash all MATCH (LOW 583)
- Base req 3: all MATCH (HIGH 713)
- Sepolia req 2: all MATCH (MEDIUM 647)

Latency (block timestamps, 2026-11-18 runs):
- request -> verdict: 10 s (worker polling cadence dominates)
- verdict -> veto/freeze callback: 1-7 s across Base/Unichain/Sepolia
- request -> all-vaults-frozen, worst observed: ~17 s
- production waitSeconds = 180 s, roughly 10x the worst observed loop.

Final state (restored after the runs):
- setWait(180) via recovery: Base 0xf03f75773f5a694b2ec77c9d4743edbb3e9aa88ec7199414f079a682fc10cbcb,
  Sepolia 0x51f15f44713db945641412113dd87f76b53036bdf54f7161a5d09d51315086ed,
  Unichain 0x1aa5aa88fb60ff49be06e6c7415632816b956d0aa53a4c73d3d5b3ef2f654de1
- print_config at restore time: balances Base 0.0120 / Sepolia 0.0080 /
  Unichain 0.0120 ETH, all unfrozen, wait 180 s, threshold 0.0040,
  cap 0.0080/3600 s; RSC reserves 0.6611 lREACT (spent ~0.34 on the runs).

## v4/v5 stack (post-audit redeploy, 2026-11-18) — CURRENT

Full self-audit (independent adversarial review + line-by-line
re-check) produced findings F1-F13; all fixed in GuardedVault v4 /
SentinelReactive v5 (38 forge tests). The VerdictRegistry was NOT
redeployed (0x0e55C8F84F44336b766Af8469b74d5163abB7F32, block
60039272) so all historical verdicts stay verifiable.

Old v3 vaults drained back to the deployer first:
- drain requests: Base id 6 (0x2a1b7aef2ca1f937947cc2c19bd7d6246dd6e719bcabc892e92072f9bee00748),
  Sepolia id 4 (0xd604f12c89a0daf520d747189a3226bd362e1fe1900823635abc748ba1fb23a7),
  Unichain id 4 (0x00c54d6cb6d1461ee0353264fd1b03c913ee8b6fc9eb13d5dc157bff5b66ec29)
- drain executes: Base 0xff9d4d64a43c2ddf4f61e2327b6678c8fb1174d59116c764a9dbfddc0ccb8391,
  Sepolia 0x4a082239a275acddb71dd04f06d70d827595eea0d12243a70bff7e26d6ca86a4,
  Unichain 0xa2d4854540cef8a822e7d4ce269c0a05f10c60ff2568a3f4445de97a67db603f
  (0.0002 ETH dust left per vault)
- lREACT top-up: 0.005 Sepolia ETH via the faucet converter
  (0x357cfb8b47c1c47368e3d7bcf448de8b09b9d389f1ca4775d1a9f7ad949b453c) -> +0.525 lREACT

Deployments:
- SentinelReactive v5 (Lasna): 0x48FA2842cCCbe70EEfD9FE094331af4f932A35A7
  deploy tx 0x0c86c1963624e0fe5ee94823c98e24a973020378220af625b6b87b461a727f8f, block 8635331,
  funded 0.8 lREACT; depositTo 0x4e7cd463423fa84a789fc2d3bc61d1c06b53cef2e43a33125e85935a2668265f
  -> reserves 1.0 lREACT (verified via reserves())
- GuardedVault v4 Base: 0xA1eDD9dBBAE962B41950F3314660e966bBEa703b
  tx 0x44302f2d3d67a195585abce226f4b03ba416fd50f6d3d78fe0df798266ea8d42, block 60328343, funded 0.02 ETH;
  watchVault 0xf219092a74e68ae1979667962436a581c3542918ab1902f7e7b5184aa0a7c009
- GuardedVault v4 Sepolia: 0x3C17336A3E7f929FEF4608fB053f539dF734B535
  tx 0x54d0599edd0b15cc4b40c62554741f7031c7d8af61a252149e827075801dd500, block 12160045, funded 0.004 ETH;
  watchVault 0x1051b8024840c65852f6887514b76cc103231cb3028e09f9660ff1f7867884d3
- GuardedVault v4 Unichain: 0x464F45Cf2bF16B1b8E454eaCDD2ff68002E58bce
  tx 0x3fdf1f129df886ee98c0b9a9a1578a0f959f9f273916b98e2e413f96c9ce8b9f, block 68135168, funded 0.012 ETH;
  watchVault 0xb1be27025f026d4c461f234103bb02504304d2fe1e40349aa3e2f85e83854c3c
- Config on all vaults: wait 180 s, threshold 0.004 ETH, cap 0.008 ETH / 3600 s
  (print_config verified; recovery funded 0.0015 ETH per chain)

### v4/v5 evidence run (2026-11-18, model iforest-3, wait temporarily 60 s)

setWait(60) x3: Base 0xc65cb5413ac4d5363eb4f8afff1dcbbd959a4ebea3f72a2f2cf2ef8c709cabb6,
Sepolia 0x71ba39f981cdd536f17c81e15f88dffcfc23039bd025d8219efe24742e968f1a,
Unichain 0x53359557dbb13b33fef04c4b17f7e17bdacd0a41c9e9829b8ee24ffab79fa17c

Negative tests (all status 0, as designed):
- attacker requestWithdrawal: 0xba697361c2be2517115634fe654a33e5d223570adae440face46474a91ea1a0f (NotOwner)
- owner unfreeze: 0x4293eca0440dbc4550be05fd5f036258a73ccf7f53874061019cc3d78b47e37c (NotRecovery)
- zero-amount request: 0x74a3a519e27ffb8186984d2fabb33e96f529cf72cdf758eb36c4fed2abbd863f (ZeroAmount, new in v4)

Case A (Base, normal loop):
- request id 1, 0.008 ETH: 0xcc8d20591294f70ad6892ca0d75d404bdb1356ddeabdf020e4b4c12149aa732a (ts 1794987716)
- Lasna RequestSeen: 0x1c5f2266203323ef9e85ff0c6fed9378ea8475e9733c8fc7128b8d5c3859b591
- verdict LOW 583: 0xcdfdc9182d473717f1b0a33987e963bf578d25702f18cb71f26833051effdfbc (ts 1794987723, +7 s)
- Lasna VerdictIgnored: 0x92c084361f1bcb75d06f1c21c5aeef8208d5bf57317be00be7986291962628ee
- executed after wait: 0xdb81ae9c5c23ebc1fd1894287e53e8de0d31a036b12afe7981f7926e8c91cd3c

Burst (Base, 3 x 0.003 ETH + cap):
- requests: id 2 0x26e0e902bab3c629edac513ca174ade4bc390184abe2ccae65899ccd3b8f0ba0,
  id 3 0x9d33177377f23f8817ff9709727e2f7164366329205d5ee1eb0592509176100d,
  id 4 0xfb8fd7754aeb8a0c39e8aa73857e5b93b8dc140cc1934066e85fd24f14d9d61a (id 4 queued by the instant cap)
- verdicts: MEDIUM 662 0x65b2a6a1293b6f82cecc909a293166cd655061ab15f5c38f516a2ccf0709a830,
  HIGH 713 0xdafeeea7a6ce89c322e234cf445a1ea240ab87ea129913944a14bc280abbad1b,
  HIGH 717 0x7f482639581576d0f551ccd35e1714f2033831b706913d0567e4cd427885681c
- Lasna reactions: MEDIUM veto 0x40411f9339d3725e8a1f78c61237e4f577fc0ea651e95fbacae06323555b0bab;
  HIGH 713 -> 0x2fab0dfd99cf4a2560efc31525f3c1668f1fdd873426851d4effaf3b28d0859a (VetoRequested + FreezeRequested x3);
  HIGH 717 -> 0xcf0d48f6ff486c1cbd6eb641a26c37d26c76d4830f8bab2649f0508f8c1bcf42 (same shape)
- callbacks on Base: veto req 2 0x52726a3bb36c1171897391465bf88ef2860c7aa14da30671fda37cb4b58e4064 (verdict +1 s),
  veto req 3 0x11683dd28e780b8459746312c90b14f8e390657db90266f7417b13503d12c2e1,
  freeze 0xd7d7a15ec52462860f989268ffefc01b935cbaed5754a4e4d55791dc5c579c15 (verdict +2 s);
  Unichain freeze 0xc8c929f25fbc6b175f4bed64963ec0125b744333cd6993433eb0941dd7ccdb03 (+2 s);
  Sepolia freeze 0x12da46b2c061335fe5ed741a840ab0b9923efd4be055b69c094b4841f4e6adc5 (+9 s)
- withdrawals(2/3/4).vetoed == true on-chain (req 3's veto is the F1 fix)

F1 proof (HIGH-flagged request cannot execute after unfreeze):
- recovery unfreeze x3: Base 0x06c38ae0c2dca2ba6d8d2c5f23bfbbaa829797e77c1d421ed2072237e7b1f3b1,
  Sepolia 0x5e7fa2c0efaa79ecb71c0d5b182f6721edde422370ff540be0aa316625014eda,
  Unichain 0xbc09836b5f09073fca26b5529ef8b71707e3edaecf067c93722afe5f9345db6c
- execute req 3 (HIGH): 0x1a46adbf1a74beeb3cc76579a235cd6df14c51e3e5da470e75de795049ac404c status 0 (Vetoed)
- execute req 2 (MEDIUM): 0x0393cd0ed02ad201283ffdd221a562c388ca7a4b18ee1862e90f05f732ac8f1d status 0 (Vetoed)

Pace build-up + pace freeze (worker down):
- Unichain reqs 1-3: 0x210eaa014d2a2eae41fceb0db02b59f2c00909e6ff36a3bef43a2773298b7693,
  0xbf259dc9d781868c4ea8d0d89d7c687543d41c248722226dcf1df21e8214444c,
  0x3e69832b2b3a265b79c31371c064ae4f0d6383c98646297129d881715829f37b
  -> LOW 522 0x4a7caf859d3a977e22159ee0f0dd0fb3dee46cb8247b8eefaf7927918c7502ce,
  LOW 611 0xc2b5128e3ce89e9df46f57911658bdca6e15f50285129ab2ed8938dabad0d478,
  HIGH 675 0xdd81a9db924f9f20e8bd89a5b2fe6df469952d468a4686c4cd78bf048bd5abbf (froze all three again)
- Sepolia req 1 (0.0005 ETH): 0xfdafbec6d9c142a2d916693e6b77f298de9ad68aa8d1bac6a4e8a13633b5055f
  (first three attempts ran out of gas at a 400k limit - Sepolia meters this call at ~710k gas,
  gasUsed 709411 on success; chain/RPC artifact, identical bytecode costs ~150k on Base)
  -> verdict LOW 571 0xa3c6423a040235461619e48ad42c618dbb38ba7ad99f8d1a457c8993a97b24f1
- Base reqs 5-6: 0x45be457b8291088d78a55b31a179b4fb6a0c054f583b6e2264ae6b2f650234d4,
  0xc023ff68b373e8b5296adeb76ec1980e0234219a9a2c167d5fa8b90acf551a47
  -> HIGH 684 0x5cde6e3a22708962f054c857dcb5ebaaed581b944614b91e5ac5950cbc112337,
  HIGH 685 0x69e732ab6b604526775ae830b71069319eb42319fef12afbcb32af3d46ba13db (both vetoed + froze all)
- 11th request (Base req 7, worker down): 0xc376f55ab175eb2997c4cbd8b1ad48b92f5cbb9f34724f82c443a6fa7fd8b0e3
  -> single Lasna tx 0xd81d1d28793290c8cab50dce0a8b1a1ffafca46a33d758a3ed9f6ae4c736be14
  (RequestSeen + PaceFreeze + FreezeRequested x3); paceCount 11, paceFrozen true;
  Sepolia freeze callback 0x98667143fe3f3396df4aa0ed8f1471533b5a568c5a6e6c5933c75144371e577b
- worker restarted afterwards: req 7 judged HIGH 685
  (0xb314eb7b5fc28435023f5e16b457584e57613e85e8e3b59878edf9cb8bdc0531); all earlier
  requests skipped via hasVerdict. (The worker process had exited during the run -
  session cleanup on the VM - and was restarted; the pace freeze above happened
  while it was down, which is the property being demonstrated.)

Cleanup:
- recovery unfreeze x3: Base 0x75d72b03457469c8b0699a6d56ae19887c4656d9f7fa6345411a390f99759c56,
  Sepolia 0xe6e7a9fa459628eeea5eff0ed8822e1f30638c79ae8f801b9604b774d96ffb08,
  Unichain 0xc1da08c89f7c84795bd576cfd697f4ed21abc1840a209d40ad1dc0f65e4bf82d
- setWait(180) x3: Base 0x7066ac23f6a3d12f220d7d92ff69b1eb964de271608da697695725782ce4b90d,
  Sepolia 0xbdab1244267c5754882833e2d34749d433886a82d670a8c0c2958cff51678112,
  Unichain 0xb0c4869bedaaf6d1d45aaa30ba3e794f7a79927d0e2bc3c46ae7166adea35151

Replay verification (scripts/replay.py, recomputed from chain data):
- Base req 1: all MATCH (LOW 583)
- Base req 3: all MATCH (HIGH 713)
- Sepolia req 1: all MATCH (LOW 571)

Latency (block timestamps, 2026-11-18 v4/v5 runs):
- request -> verdict: 7 s
- verdict -> veto/freeze callback: 1-9 s (Sepolia slowest)
- request -> all-vaults-frozen, worst observed: ~16 s; waitSeconds 180 s (~10x margin)

Final state: balances Base 0.0200 / Sepolia 0.0040 / Unichain 0.0120 ETH
(minus callback fees paid during the runs), all unfrozen, wait 180 s,
threshold 0.0040, cap 0.0080/3600 s; RSC balance 0.8000 lREACT, reserves 1.0000 lREACT.

### Deliberate pace-freeze re-run (2026-11-18 evening) — the run the README/video cite

The first pace freeze above happened while the worker was down (it
had exited on its own). To have the flagship claim rest on a
deliberate demonstration, the pace run was repeated with the worker
intentionally stopped and verified stopped (process count 0) before
the final request:
- new pace window (windowStart 1794992216); build-up of 10 requests
  across the three vaults with the worker live (several model HIGHs
  froze the vaults mid-build; recovery unfreezes between attempts)
- worker killed and verified stopped; vaults unfrozen
- 11th request (Base id 13, 0.001 ETH): 0x6372657ffae7f10e03ae249a3239bc86ec406fc5aa0a61a64e9d60d5f8253167 (ts 1794992466)
- single Lasna tx 0xfd8edbf5953271d69daaa589430e38bfed6c2c2a70f876d99c9f6bc6f1fc7060:
  RequestSeen + PaceFreeze + FreezeRequested x3 (paceCount 11, paceFrozen true)
- freeze callbacks: Base 0x40ccd8e78c61bab469b9329ae93e702a653463e5bf31a2cf3b73e3c6187cda7c (+2 s),
  Unichain 0x81f9bc88dcfcb9ee7fdaccc53fde5b75426adde26a2bc9def0138089ee48e9f4 (+3 s),
  Sepolia 0x0a32adcd399f681888ce9be891bc1fc8fff41509d0f1ae71655d88185a850f1e (+6 s)
- recovery unfreeze x3 afterwards: Base 0x00a4a178d4b62ff247477f99c8f56db4f7eb23c9cfd00e1c6778fb702e814ab7,
  Sepolia 0xadc444250d932b1f013c39ebf27b91be47589146a2f72384de5bf6e24496cd4b,
  Unichain 0xffa9c92469013b44e58515fe35a64adb963aff2b44a2cf00868d9d62cdb5b990;
  worker restarted.

### Final state after the full re-verification (2026-11-18 evening)
- Reserves top-up: depositTo 0.04 lREACT, tx
  0x72efcd47dfdabb74206070857984a60f34fd284a279de0a2b585f418dce921ef
  -> reserves 0.2865 lREACT. (A full restore to 1.0 was not possible:
  the evidence programme spent the deployer's testnet funds - it holds
  0.0009 Sepolia ETH - and ~0.01 lREACT per callback cycle means the
  remaining reserves cover dozens of further judging cycles.)
- Final recovery unfreezes (after the restarted worker finished
  judging the pace build-up backlog): Base
  0x43ee7f1c6ba77f4a168dc77608b5ee659fead5cc889d16e2bf5d9398bc36820b,
  Sepolia 0x75646ebed30d38311933aca30a889848546a57dad39c2c91be5a4e751e6b244f,
  Unichain 0x177d72e1e82255adb34554c7d07e6a2a35a771af4a7da72f92a7c2be72905019.
  Verified 75 s later and again at the final print_config: all three
  vaults frozen=false, config 180 s / 0.004 / 0.008 per 3600 s,
  balances Base 0.0120 / Sepolia 0.0040 / Unichain 0.0120 ETH.
- Re-verification summary: forge test 38/38; eval re-run byte-identical;
  modelHash re-derived == on-chain; replay MATCH x4 (Base req 1 LOW 583,
  Base req 3 HIGH 713, Base req 5 HIGH 684, Sepolia req 1 LOW 571) plus
  MATCH from a clean clone with no .env present; gitleaks git history
  clean (the only working-tree findings are the 4 keys in the
  gitignored .env itself); all commits authored Muse <muse@local>,
  first commit 2026-11-17, inside the event period.
