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
Local file ready: video/demo.mp4 (1280x720, English narration + burned-in captions; v6 rebuild 2026-11-18 with animated scenes and explorer-data cards from the v5/v6 evidence run in docs/deployments.md). Upload to YouTube (unlisted) or DoraHacks and paste the URL here.

## Repo
https://github.com/kk11121/sentinel-vault

## Owner checklist at submission time
1. Create DoraHacks account (if not yet) and register for the buildathon.
2. Create the GitHub repo (public) — Muse provides the clean tree.
3. Upload the demo video, paste its URL above.
4. Submit the build in the AI track with this packet's fields.
5. (Parallel) Check the DoraHacks Q&A for the organizer's eligibility answer (posted 2026-11-17).
