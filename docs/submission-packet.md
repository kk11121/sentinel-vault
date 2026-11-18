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

## Contract addresses
- VerdictRegistry — Base Sepolia: 0x0e55C8F84F44336b766Af8469b74d5163abB7F32
- SentinelReactive (RSC) — Lasna: 0xeaE20eccD1F308CaB3e8a4c99e588D8CC21a1ff8
- GuardedVault — Base Sepolia: 0xAf17d1e294c35cA4eFE35c58B201D6F95Aef3DE4
- GuardedVault — Ethereum Sepolia: 0x0C0c54778431652a2c6b92E088fB02335d395BED
- GuardedVault — Unichain Sepolia: 0x95Fd0764a2f75387F35c8eEAB409aa1410b19b2d
- modelHash: 0x0dfa7cb105d6c64d39889abc4926fc514b0cccf075c9e3071ddff893fcfd45c5 (model iforest-3)

## Transaction links (full loop evidence)
Use the "Proof" section of README.md (request -> verdict -> execute /
veto / freeze, plus the failed attacker direct-freeze tx).

## Demo video
2-3 min, English subtitles, no owner voice. Script: docs/demo-runbook.md.
Local file ready: video/demo.mp4 (2m22s, 1280x720, English narration + burned-in captions; v4 rebuild 2026-11-18 with animated scenes and explorer-data cards from the evidence run in docs/deployments.md). Upload to YouTube (unlisted) or DoraHacks and paste the URL here.

## Repo
[GitHub URL to fill after the owner creates/pushes — public, MIT]

## Owner checklist at submission time
1. Create DoraHacks account (if not yet) and register for the buildathon.
2. Create the GitHub repo (public) — Muse provides the clean tree.
3. Upload the demo video, paste its URL above.
4. Submit the build in the AI track with this packet's fields.
5. (Parallel) Check the DoraHacks Q&A for the organizer's eligibility answer (posted 2026-11-17).
