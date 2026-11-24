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
  that the text matches the numbers. Two rules keep the text honest:
  every feature the rationale mentions is cited as `name value`
  (e.g. `interval_log 1.80`), and before a rationale is kept, every
  number in it is traced mechanically to the record with
  `scripts/check_rationale.py`. The check was tightened on
  2026-11-24 (external review): there is no tolerance band — a
  number must equal a record value exactly at the precision the
  text writes it (the old ±1% band would have let "626" pass for a
  score of 590, being within 1% of the 620 threshold); derived
  figures, such as the gap in hours, are computed by the checker
  itself from record fields (`ts` and `prev_request_ts`) — the
  writer-declared `allowed_extra` field is abolished, and an entry
  still carrying it fails; plain-language claims are checked too
  (a "below the MEDIUM threshold" must be true of the score, a
  "first-seen destination" must agree with `first_seen`); and with
  `--onchain` the entry is compared against the verdict's
  `VerdictPosted` log (chain, vault, requestId, severity, score —
  and `featuresHash`, recomputed from the entry's vector when the
  vector is stored at full precision; entries whose vector is
  rounded to 2 decimal places, as the worker log renders it,
  cannot reproduce the hash, which commits to full-precision
  floats — for those, `scripts/replay.py` is the full check, as it
  recomputes the features from chain data). A rationale that fails
  the check is revised once; if it fails again, the entry is
  stored with `rationale: null` and `checked: false` — an
  unexplained verdict is recorded as such, never dressed up.
- **Observations — watching what the model cannot see:** the model
  judges each vault from its own chain's history and has no
  time-of-day feature, so the explainer also files a short
  `observations` note from outside the feature vector: the other
  vaults' recent requests and frozen state, the request's hour,
  and the destination's footprint on the other chains. An
  observation cannot change any verdict; it is a second set of
  eyes for the human record, and it must state the limits of its
  own read (for example, Ethereum Sepolia's early history cannot
  currently be re-read — its public RPC has pruned that range).
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

Observation filed with it:

> Cross-chain, nothing stood out: no requests on the Unichain
> vault since the 2026-11-18 evidence programme, and no freeze or
> callback activity on Ethereum Sepolia either (its recent
> history cannot be re-read — the public RPC has pruned that
> range — so this rests on the absence of observed events, not a
> full rescan). The request arrived at 12:01 JST, an unremarkable
> hour for this vault. The model's same-chain view missed none of
> this, because there was nothing to miss.
