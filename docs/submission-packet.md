# DoraHacks submission packet — Reactive Omni Buildathon, AI track
# (drafts; owner submits. Internal deadline 2026-12-05 18:00 JST)

## Project name
Sentinel Vault

## Tagline (one line)
An off-chain model decides; a Reactive contract enforces. The model's key can post verdicts and nothing else — it cannot move, unfreeze, or reconfigure the vaults.

## Description (long form, for the submission page)
See README.md — reuse its "Why this design" and "How it works"
sections verbatim. Key claims, all verifiable on-chain:
- AI judges, contract executes: Isolation Forest verdicts on-chain;
  the Lasna RSC converts them into vetoes/freezes via callbacks.
- Least privilege: the verdict-writer key can only post verdicts;
  veto/freeze are reachable only through callback proxies with the
  RSC as injected sender. A leaked AI key can freeze, never steal.
- Fail-open: if the AI is silent, queued withdrawals execute after
  the timelock. Bounded damage, auditable after the fact (replay
  tool reproduces any verdict bit-for-bit).
- Honest eval: rule-vs-model numbers published as computed,
  including the model's false alarms (eval/RESULTS.md).

## Contract addresses (current stack: GuardedVault v5 / SentinelReactive v6, 2026-11-18)
- VerdictRegistry — Base Sepolia: 0x0e55C8F84F44336b766Af8469b74d5163abB7F32
- SentinelReactive (RSC) — Lasna: 0x00eC75c154EF87A38836819594c0F2898cF3Eb06
- GuardedVault — Base Sepolia: 0x1Eb81CC9a9b9760D1DA575C268c47f727369c6f4
- GuardedVault — Ethereum Sepolia: 0xd8D640DeEcD14DA46b78e29285cdc682BA118Ad6
- GuardedVault — Unichain Sepolia: 0xAf17d1e294c35cA4eFE35c58B201D6F95Aef3DE4
- modelHash: 0x0dfa7cb105d6c64d39889abc4926fc514b0cccf075c9e3071ddff893fcfd45c5 (model iforest-3)

## Transaction links (full loop evidence)
Use the "Proof" section of README.md (request -> verdict -> execute /
veto / freeze, plus the failed negative tests: non-owner request,
owner unfreeze attempt, zero-amount request).

## Demo video
2-3 min, English subtitles, no owner voice. (docs/demo-runbook.md is
historical — it describes the pre-audit shoot.)
Local file ready: video/demo.mp4 (1280x720, 2m20s, English narration + burned-in captions; v7 polish 2026-11-19: tighter pacing, quiet procedural BGM ducked under the narration, soft accents at the veto/freeze/match moments; scenes and explorer-data cards from the v5/v6 evidence run in docs/deployments.md). As submitted 2026-11-19: the DoraHacks video field accepts URLs only (no direct file upload), so the BUIDL's Video link is the commit-pinned jsDelivr URL of the file in this repo: https://cdn.jsdelivr.net/gh/kk11121/sentinel-vault@21cd6d3/video/demo.mp4 (serves video/mp4; the form's missing-video warning cleared).

## Repo
https://github.com/kk11121/sentinel-vault

## Owner checklist at submission time
1. Create DoraHacks account (if not yet) and register for the buildathon.
2. Create the GitHub repo (public) — Muse provides the clean tree.
3. Upload the demo video, paste its URL above.
4. Submit the build in the AI track with this packet's fields.
5. (Parallel) Check the DoraHacks Q&A for the organizer's eligibility answer (posted 2026-11-17).

## Organizer questions — as entered in the DoraHacks form (2026-11-19)
BUIDL: https://dorahacks.io/build/51326 — Track: Reactive Meets AI.
Looking for teammates: No. (Recorded here because the answers otherwise
exist only inside the submission form.)

1. **Deployed contract addresses, and which network (Reactive mainnet or Lasna)?**
   "All contracts are on testnets. VerdictRegistry — Base Sepolia: 0x0e55C8F84F44336b766Af8469b74d5163abB7F32. SentinelReactive (RSC) — Lasna (Reactive testnet): 0x00eC75c154EF87A38836819594c0F2898cF3Eb06. GuardedVault — Base Sepolia: 0x1Eb81CC9a9b9760D1DA575C268c47f727369c6f4. GuardedVault — Ethereum Sepolia: 0xd8D640DeEcD14DA46b78e29285cdc682BA118Ad6. GuardedVault — Unichain Sepolia: 0xAf17d1e294c35cA4eFE35c58B201D6F95Aef3DE4."
2. **Transaction hashes showing the full loop, from origin event to callback.**
   (The form caps this answer at 960 characters, so the text actually entered is the 949-character version below; the complete set follows it for the record.)
   "Base Sepolia, normal loop: request 0xa2cd8b68b61ad93e625eff3e301ea114fad397efed63584fda07b7dba6c9bad1 -> RequestSeen (Lasna) 0x589c68f64444d44da62add21a7376c49d01ae7558bf6ee12210a3d4b06650907 -> verdict LOW (522) 0x6f3da7d62fbaf6d31561140743520b47f4457fefffb3a4a8b4c83386c3480a59 -> executed 0xbaa2fa62505484a764f7ad955c6e040d5cc7460e2710d64c39388dc38cee4e23. Ethereum Sepolia, MEDIUM veto: verdict MEDIUM (624) 0x98ef6e728f86a251dc807aaebbe5a6c18c76c30936d9b8987e38df5327a17716 -> veto callback 0x9c2206e572e6eed55e02b0795137e8bc334c4d894aed508c675e370f05b9cf01. Base, HIGH veto + freeze-all: verdict HIGH (735) 0x5d192de11fb1cf251c67b29a381c60fa28685d56d8a0997ba638654369aad3ae -> veto callback 0x9c981fc16bf685444d6408f376f6ebfbbb2b16bf60c26f2fe5c4bd09435cfaec -> freeze callback 0xf8393de45fa91bfa65492145a419be8d629bce2e6f3ce561bf4748c0b365ee03. Full set incl. escalation and the reverted execution, with explorer links: README 'Proof' section."
   Complete set — full hashes with explorer links, transcribed from the README "Proof — the full loop on-chain" section. Base Sepolia normal loop: request 0xa2cd8b68b61ad93e625eff3e301ea114fad397efed63584fda07b7dba6c9bad1 → RequestSeen (Lasna) 0x589c68f64444d44da62add21a7376c49d01ae7558bf6ee12210a3d4b06650907 → verdict LOW (522) 0x6f3da7d62fbaf6d31561140743520b47f4457fefffb3a4a8b4c83386c3480a59 → executed 0xbaa2fa62505484a764f7ad955c6e040d5cc7460e2710d64c39388dc38cee4e23 (the Unichain loop is listed alongside). Ethereum Sepolia MEDIUM veto: request 0xb8b18050a72f56ef146e94755fd7cfe37360394012c9c53e4cbd20179784c14b → verdict MEDIUM (624) 0x98ef6e728f86a251dc807aaebbe5a6c18c76c30936d9b8987e38df5327a17716 → veto callback 0x9c2206e572e6eed55e02b0795137e8bc334c4d894aed508c675e370f05b9cf01; escalation verdict MEDIUM (627) 0x24ecf1156640dc778e0ed81266ce670a7390311820b3efc047444ca4b02724cc with the Lasna Escalated event in 0xb931eedff1fe486247c331a9cc363171280e4c42bf0125e51660abf60e847311. Base HIGH veto + freeze-all: verdict HIGH (735) 0x5d192de11fb1cf251c67b29a381c60fa28685d56d8a0997ba638654369aad3ae, veto callback 0x9c981fc16bf685444d6408f376f6ebfbbb2b16bf60c26f2fe5c4bd09435cfaec, freeze callback 0xf8393de45fa91bfa65492145a419be8d629bce2e6f3ce561bf4748c0b365ee03, verdict HIGH (700) 0x583e8b1c7c0e3d0eec4fdb665de33a21c12cda614ca28f5f670cd6602d6f5945, and the post-unfreeze execution of the vetoed request reverting 0x66bc581d4dbf3150542f58659082eeed6bd6e81e6082ed109dec5188b7dd7346.
3. **For Every Second Counts: what full-loop latency did you measure, and how?**
   "This entry is in the Reactive Meets AI track, not Every Second Counts. For reference, our measured request-to-verdict latency was about 11 seconds on Base Sepolia and about 40 seconds on Ethereum Sepolia, measured from the block timestamps of the withdrawal-request transaction and the on-chain verdict transaction (see the 'Measured latency' table in the repo README)."
4. **Was this your first time building with Reactive? Your first smart contract?**
   "Yes — this was our first time building with Reactive, and the smart contracts in this repository were written from scratch during the buildathon. Everything in the repo was built during the event period."
5. **What was the hardest part of building with Reactive?**
   "The Lasna migration to the Omni fork. Much of the public documentation and the public reactive-lib still describe the legacy RVM model, so we verified the current RPC and explorer endpoints, the system-contract interface, and the callback-proxy authorization model against the live network, and reimplemented minimal Omni base contracts ourselves. After that, the subscribe → react → callback loop itself worked as documented."
6. **How did you hear about the buildathon?**
   "Recommended by an AI assistant while researching buildathons."
