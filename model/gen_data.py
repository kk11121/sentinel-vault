"""Synthetic normal-behaviour generator for training and evaluation.

Two vault personalities (see A' design):
  daily-small:    ~2 withdrawals/day, small amounts, few destinations,
                  business hours.
  monthly-large:  ~3 withdrawals/month, large amounts, 2 destinations.
Only *normal* behaviour is generated here; attacks live in eval/.

Generator v2 (large_known=True) adds one realistic pattern v1 lacked:
occasional LARGE payments to a KNOWN destination (a quarterly tax
payment, a big vendor invoice — roughly 2-5x the median). In v1 data
"large" only ever co-occurred with the amount distribution's tail, and
the shipped v1 model answered a 3x-median payment to a known address
with HIGH (a full freeze). v2 teaches the model that large-to-known is
part of normal life for both personalities.
"""
import random

PERSONALITIES = {
    "daily-small": {
        "median_amount": 0.01,
        "median_interval_seconds": 43_200,
        "amount_sigma": 0.45,
        "destinations": ["0xKnownA", "0xKnownB", "0xKnownC"],
        "dest_weights": [0.5, 0.3, 0.2],
        "balance": 0.5,
        "active_hours": (8, 19),
        "new_dest_prob": 0.01,
        "large_known_prob": 0.02,
    },
    "monthly-large": {
        "median_amount": 0.2,
        "median_interval_seconds": 864_000,
        "amount_sigma": 0.35,
        "destinations": ["0xKnownA", "0xKnownB"],
        "dest_weights": [0.6, 0.4],
        "balance": 5.0,
        "active_hours": (9, 17),
        "new_dest_prob": 0.005,
        "large_known_prob": 0.05,
    },
}


def gen_history(personality, days=180, seed=42, large_known=False):
    """Returns (profile, history, balances) — history is a list of
    (timestamp, to, amount); balances[i] is the vault balance just
    before history[i] (balance is topped back up by deposits, modelled
    as returning to the personality's typical level).

    large_known=False reproduces the v1 generator exactly (same seeds,
    same draws); True enables the v2 large-to-known pattern."""
    rng = random.Random(seed)
    p = PERSONALITIES[personality]
    profile = {
        "median_amount": p["median_amount"],
        "median_interval_seconds": p["median_interval_seconds"],
        "known_destinations": list(p["destinations"]),
    }
    history, balances = [], []
    t = 1_700_000_000  # fixed epoch for reproducibility
    end = t + days * 86_400
    fresh = 0
    while t < end:
        # interval ~ lognormal around the median interval
        interval = p["median_interval_seconds"] * rng.lognormvariate(0, 0.5)
        t += interval
        # snap to active hours
        hour = (t % 86_400) / 3600
        lo, hi = p["active_hours"]
        if not (lo <= hour < hi):
            t += ((lo - hour) % 24) * 3600
        if rng.random() < p["new_dest_prob"]:
            fresh += 1
            to = f"0xFresh{fresh}"
            amount = p["median_amount"] * rng.lognormvariate(0, p["amount_sigma"])
        elif large_known and rng.random() < p["large_known_prob"]:
            # rare but legit: a big payment to a regular destination
            to = rng.choices(p["destinations"], p["dest_weights"])[0]
            amount = p["median_amount"] * rng.lognormvariate(1.1, 0.35)  # ~3x median
        else:
            to = rng.choices(p["destinations"], p["dest_weights"])[0]
            amount = p["median_amount"] * rng.lognormvariate(0, p["amount_sigma"])
        balances.append(p["balance"])
        history.append((int(t), to, round(amount, 6)))
    return profile, history, balances
