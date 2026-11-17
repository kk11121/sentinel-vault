# DoraHacks submission packet — Reactive Omni Buildathon, AI track
# (drafts; owner submits. Internal deadline 2026-12-05 18:00 JST)

## Project name
Sentinel Vault

## Tagline (one line)
An AI-guarded vault where the model's key can never touch the funds —
and a Reactive contract, not a server, does the stopping.

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
- VerdictRegistry — Base Sepolia: 0xEe60c9776CAc32bda21ED7e6cAD1497717B28A12
- SentinelReactive (RSC) — Lasna: 0x946181Feb969e29cA42aF5dB0b17325CA524262e
- GuardedVault — Base Sepolia: 0xFf25f82b50c0164D815D0d18037afab502D2b926
- GuardedVault — Ethereum Sepolia: 0x95Fd0764a2f75387F35c8eEAB409aa1410b19b2d
- GuardedVault — Unichain Sepolia: 0x68A10a67C79593d6e4a69AB7Abc5762380Dc5560
- modelHash: 0xc65a9db604e61be432fe2822e9cbcdfd97f75698593372377b1987dc5b5f6bb7

## Transaction links (full loop evidence)
Use the "Proof" section of README.md (request -> verdict -> execute /
veto / freeze, plus the failed attacker direct-freeze tx).

## Demo video
2-3 min, English subtitles, no owner voice. Script: docs/demo-runbook.md.
[URL to fill after upload]

## Repo
[GitHub URL to fill after the owner creates/pushes — public, MIT]

## Owner checklist at submission time
1. Create DoraHacks account (if not yet) and register for the buildathon.
2. Create the GitHub repo (public) — Muse provides the clean tree.
3. Upload the demo video, paste its URL above.
4. Submit the build in the AI track with this packet's fields.
5. (Parallel) Post the eligibility question if still unanswered.
