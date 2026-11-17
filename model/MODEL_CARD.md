# Model Card — Sentinel Vault anomaly model (iforest-1)

## What it is
A one-class **Isolation Forest** (scikit-learn, 100 trees, max_samples
128) that scores every withdrawal request from a GuardedVault and maps
the score to LOW / MEDIUM / HIGH. The worker posts the verdict on-chain;
the Reactive contract (not the model) executes veto/freeze. The model's
key can never move funds.

The forest is exported as plain JSON (`model/model.json`, ~139 KB — no
pickle) and scored by a pure-python implementation (`model/scorer.py`)
whose ranking matches sklearn's (Spearman −0.9999 on held-out data).
`modelHash = keccak256(model.json)` =
`0xc65a9db604e61be432fe2822e9cbcdfd97f75698593372377b1987dc5b5f6bb7`
is posted with every verdict, so the exact model that judged a
withdrawal is identifiable and replayable (`scripts/replay.py`).

## Features (model/features.py — one shared code path)
1. `amount_ratio` — log1p(amount / profile median amount)
2. `first_seen` — destination never observed for this vault
3. `interval_log` — log1p(time since last withdrawal / profile median interval)
4. `count_1h` — withdrawals in the last hour (capped)
5. `sum_1h_ratio` — log1p(sum of last hour's amounts / profile median amount)
6. `balance_ratio` — amount / vault balance at request time

A *profile* encodes what normal looks like (median amount/interval,
known destinations). Two training personalities: `daily-small`
(~2 withdrawals/day, median 0.01 ETH) and `monthly-large` (~3/month,
median 0.2 ETH). The deployed worker uses `daily-small` plus the
operator's own addresses as known destinations.

## Training data — synthetic, disclosed
Trained **only on synthetic normal behaviour** (398 withdrawals from
`model/gen_data.py`, fixed seeds): lognormal amounts/intervals around
each personality's medians, a handful of known destinations, business
hours. No real user data exists for this system; the generator is in
the repo so anyone can regenerate the exact training set
(`model/train.py`).

## Thresholds
Calibrated on training scores from the shipped scorer:
MEDIUM ≥ 598, HIGH ≥ 655 (97.5th / 99.5th percentile of normal
training scores, score = 1000·2^(−E[path]/c(128))).

## Evaluation summary (eval/RESULTS.md, synthetic, reported as-is)
- Held-out normal traffic flagged ≥MEDIUM: rule-v1 0.8%, **model 3.8%**
  — the model is more trigger-happy; that is a real cost.
- Full drain: both methods flag HIGH on the 1st withdrawal.
- Small-amount barrage: both flag at #1; only the model escalates to
  HIGH (the fixed rule is blind to amount patterns below its threshold).
- Concentration to one new address: rule reaches HIGH, model only
  MEDIUM (each withdrawal is still vetoed, and a 2nd MEDIUM escalates
  to a freeze on-chain by design).
- Rare-but-legit, 3× median to a known address: rule passes (LOW),
  **model flags HIGH** — a genuine false alarm, kept in the report.
- Rare-but-legit, normal amount after a 30-day pause: both LOW.

## Limitations
- Synthetic training data; no claim of performance on real vaults.
- `balance_ratio` dominates when a vault is nearly empty (as with the
  demo vaults): small withdrawals from a tiny balance look drain-like.
- No time-of-day feature; hour-of-day anomalies are invisible to it.
- A HIGH verdict freezes funds until the owner unfreezes — safe
  direction, but false HIGHs are operationally costly by design.

## Reproduce
```
.venv/bin/python model/train.py        # regenerates model.json + hash
.venv/bin/python eval/run_eval.py      # regenerates eval/RESULTS.md
.venv/bin/python scripts/replay.py --chain 11155111 --request-id 1
```
