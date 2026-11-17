# Model Card — Sentinel Vault anomaly model (deployed: iforest-3)

## What it is
A one-class **Isolation Forest** (scikit-learn, 100 trees, max_samples
128) that scores every withdrawal request from a GuardedVault and maps
the score to LOW / MEDIUM / HIGH. The worker posts the verdict on-chain;
the Reactive contract (not the model) executes veto/freeze. The model's
key can never move funds.

The forest is exported as plain JSON (`model/model.json`, ~137 KB — no
pickle) and scored by a pure-python implementation (`model/scorer.py`)
whose ranking matches sklearn's (Spearman −0.9999 on held-out data;
the correlation is negative because the two implementations' score
directions are opposite — sklearn's anomaly score decreases as the
pure-python score1000 increases). `modelHash = keccak256(model.json)` =
`0x0dfa7cb105d6c64d39889abc4926fc514b0cccf075c9e3071ddff893fcfd45c5`
is posted with every verdict, so the exact model that judged a
withdrawal is identifiable and replayable (`scripts/replay.py`).

## Version history (all files kept in the repo)
- **iforest-1** (`model_v1.json`, hash 0xc65a9db6…): shipped at M3.
  Generator-v1 training data, 6 features, thresholds from training
  percentiles. Its false HIGHs on held-out normal traffic (6 of 236,
  all large payments to known addresses) motivated v2.
- **iforest-2** (`model_v2.json`, hash 0x83de2700…): generator-v2 data
  (adds rare large-to-known payments), thresholds calibrated on a
  dedicated set. Zero false HIGHs on daily-small — but the v2
  evaluation exposed a total blind spot: a slow drain to an
  already-known address at a 10-minute pace scored LOW on all 20
  steps, because the 1-hour pace features plateau as the window slides.
- **iforest-3** (`model_v3.json` = the deployed `model.json`): v2's
  recipe + features f7/f8 (24-hour pace aggregates). Flags the slow
  drain at step 2, keeps zero false HIGHs on every held-out set, and
  passes both rare-legit probes as LOW. Adopted under the criteria in
  `eval/RESULTS.md` — including one criterion it fails (concentration
  flagged one step later than v2), with the override stated there.

## Features (model/features.py — one shared code path)
1. `amount_ratio` — log1p(amount / profile median amount)
2. `first_seen` — destination never observed for this vault
3. `interval_log` — log1p(time since last withdrawal / profile median interval)
4. `count_1h` — withdrawals in the last hour (capped)
5. `sum_1h_ratio` — log1p(sum of last hour's amounts / profile median amount)
6. `balance_ratio` — amount / vault balance at request time
7. `count_24h` — withdrawals in the last 24 hours (capped)
8. `sum_24h_ratio` — log1p(sum of last 24 hours' amounts / profile median amount)

A *profile* encodes what normal looks like (median amount/interval,
known destinations). Two training personalities: `daily-small`
(~2 withdrawals/day, median 0.01 ETH) and `monthly-large` (~3/month,
median 0.2 ETH). The deployed worker uses `daily-small` plus the
operator's own addresses as known destinations (the list is committed
at `worker/known_destinations.json`).

## Training data — synthetic, disclosed
Trained **only on synthetic normal behaviour** (394 withdrawals from
`model/gen_data.py` generator v2, fixed seeds): lognormal
amounts/intervals around each personality's medians, a handful of
known destinations, business hours, and rare large payments to known
destinations (~2–5% of traffic). No real user data exists for this
system; the generator is in the repo so anyone can regenerate the
exact training set (`model/train_v3.py`).

## Thresholds
Calibrated with the shipped scorer on a dedicated calibration set
(generator v2, seed 1234, disjoint from training and evaluation):
MEDIUM ≥ 620, HIGH ≥ 670 (97.5th / 99.5th percentile of calibration
scores, score = 1000·2^(−E[path]/c(128))).

## Evaluation summary (eval/RESULTS.md, synthetic, reported as-is)
- Held-out normal traffic, daily-small (n=236): model-v3 flags
  ≥MEDIUM in 4 cases, HIGH in **0**. model-v1 flagged 9 (6 HIGH);
  rule-v1 flags 2.
- Full drain, barrages: flagged at #1 by all models.
- Slow drain to a known address (the v1/v2 blind spot): only v3
  flags it (step 2). rule-v1 never flags it — its first branch trusts
  any destination in the request history.
- Two personalities, one rule: on monthly-large, rule-v1 answers a
  routine first payment to a new vendor with HIGH (full freeze);
  v3 says LOW, and still catches the full drain.
- Concentration to one new address: v3 flags at #2, one step later
  than v2 — recorded, not hidden.

## Limitations
- Synthetic training data; no claim of performance on real vaults.
- `balance_ratio` dominates when a vault is nearly empty (as with the
  demo vaults): small withdrawals from a tiny balance look drain-like.
- No time-of-day feature; hour-of-day anomalies are invisible to it.
- A still slower drain (e.g. one sub-threshold withdrawal per day to
  a known address) is not detected by any method evaluated here;
  the on-chain instant cap and the RSC pace guard bound its speed,
  and the residual risk is accepted and disclosed.
- A HIGH verdict freezes funds until the recovery key unfreezes —
  safe direction, but false HIGHs are operationally costly by design.

## Reproduce
```
.venv/bin/python model/train_v3.py     # regenerates model_v3.json + hash
.venv/bin/python eval/run_eval.py      # regenerates eval/RESULTS.md
.venv/bin/python scripts/replay.py --chain 11155111 --request-id 1
```
