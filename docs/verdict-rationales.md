# Verdict rationales — the LLM explains, the small model decides

Every verdict the worker posts is accompanied by a short
plain-language rationale, written by an LLM **after** the verdict is
already on-chain. The rationale is commentary, not authority:

- **Who decides:** the Isolation Forest (`model/model.json`), exactly
  as before. Severity and score are computed deterministically from
  the 8 numeric features and are reproducible bit-for-bit with
  `scripts/replay.py`. The LLM has no path to the verdict: it cannot
  raise, lower, delay, or block one.
- **What the LLM reads:** only the numeric record of the verdict —
  the feature vector (amount_ratio, first_seen, interval_log,
  count_1h, sum_1h_ratio, balance_ratio, count_24h, sum_24h_ratio),
  the score, the severity, and the request facts (chain, amount,
  destination). It never reads text an attacker controls (there is
  none in the pipeline), so the prompt-injection surface stays zero,
  and its prompt template is fixed.
- **When:** after the verdict transaction confirms. If the explainer
  is unavailable, verdicts continue without rationales — enforcement
  never depends on it.
- **Checking the words:** rationales are stored in
  `worker/rationales.jsonl`, one JSON line per verdict, next to the
  exact feature vector and score they describe, so anyone can verify
  that the text matches the numbers.
- **Production mapping:** in a production deployment this step is a
  hosted LLM API call in the same slot (post-verdict, numeric input
  only). During this buildathon's judging period it is performed by
  the operator's scheduled AI agent run, which appends the rationale
  for each day's heartbeat verdict; this is disclosed here rather
  than presented as an API integration it is not.

## Sample — Base Sepolia request 12 (2026-11-21, the heartbeat primer)

Record: 0.001 ETH to the owner (a known destination); verdict
**MEDIUM, score 632** (thresholds: MEDIUM 620, HIGH 670); features
[amount_ratio 0.10, first_seen 0.00, interval_log 1.80, count_1h
0.00, sum_1h_ratio 0.00, balance_ratio 0.09, count_24h 0.00,
sum_24h_ratio 0.00]; verdict tx
`0b9caf6524576d0071c0f8d70ea3865d96f618fd911e4553ba5907a744a45cc7`.

Rationale as generated:

> This request was vetoed (MEDIUM) almost entirely because of
> timing, not amount or destination. It was the vault's first
> withdrawal request in about 61 hours — roughly five times the
> profile's median interval — and the model treats the first move
> after a long silence as the moment a stolen key would act
> (interval_log 1.80 is the dominant feature). Everything else is
> quiet: the amount is small (0.001 ETH, about 9% of the vault
> balance), the destination is the owner's own long-known address
> (first_seen 0), and there is no burst pattern — no other requests
> in the last hour or the last day. A single MEDIUM vetoes only
> this request and freezes nothing; the same request made a day
> later, with the interval back to normal, scores LOW and
> executes.
