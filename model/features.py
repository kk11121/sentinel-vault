"""Shared feature computation for the Sentinel Vault anomaly model.

Used identically by training (model/train.py), the live worker
(worker/worker.py) and the replay tool (scripts/replay.py), so a verdict
can always be recomputed after the fact from the same code path.

A *profile* encodes what "normal" looks like for a vault (learned from
its history; the shipped profiles are documented in MODEL_CARD.md).
Event-dependent features come from the live observed state.

Feature vector (6):
  f1 amount_ratio   log1p(amount / profile.median_amount)
  f2 first_seen     1.0 if destination never observed (and not a profile
                    known destination), else 0.0
  f3 interval_log   log1p(seconds_since_last_withdrawal /
                    profile.median_interval_seconds); neutral log1p(1)
                    when there is no prior withdrawal
  f4 count_1h       withdrawals in the last hour, capped at 10, / 10
  f5 sum_1h_ratio   log1p(sum of amounts in the last hour /
                    profile.median_amount)
  f6 balance_ratio  amount / vault balance just before the request
"""
import math
from statistics import median

FEATURE_NAMES = [
    "amount_ratio",
    "first_seen",
    "interval_log",
    "count_1h",
    "sum_1h_ratio",
    "balance_ratio",
]

# Shipped reference profiles (see MODEL_CARD.md). Amounts in wei-scale
# agnostic units: the demo vaults operate in ETH, so units are ETH here.
PROFILES = {
    "daily-small": {
        "median_amount": 0.01,
        "median_interval_seconds": 43_200,  # ~2 withdrawals/day
        "known_destinations": [],
    },
    "monthly-large": {
        "median_amount": 0.2,
        "median_interval_seconds": 864_000,  # ~3 per month
        "known_destinations": [],
    },
}


def compute_features(profile, history, to, amount, timestamp, balance):
    """history: list of (timestamp, to, amount) past withdrawals, sorted.
    Returns the 6-float feature list for a new request."""
    med_amt = profile["median_amount"]
    med_int = profile["median_interval_seconds"]

    f1 = math.log1p(amount / med_amt)

    known = {h[1] for h in history} | set(profile.get("known_destinations", []))
    f2 = 0.0 if to in known else 1.0

    if history:
        since_last = max(0, timestamp - history[-1][0])
        f3 = math.log1p(since_last / med_int)
    else:
        f3 = math.log1p(1.0)

    last_hour = [h for h in history if timestamp - h[0] < 3600]
    f4 = min(len(last_hour), 10) / 10.0
    f5 = math.log1p(sum(h[2] for h in last_hour) / med_amt)

    f6 = amount / balance if balance > 0 else 1.0

    return [f1, f2, f3, f4, f5, f6]


def features_hash(features, amount, to, first_seen):
    """Deterministic hash of the feature vector + raw inputs, posted
    on-chain with each verdict so replay can verify it."""
    from web3 import Web3

    packed = b"".join(
        int(round(f * 1_000_000)).to_bytes(8, "big", signed=True) for f in features
    )
    packed += amount.to_bytes(32, "big")
    packed += bytes.fromhex(to[2:].rjust(40, "0"))
    packed += b"\x01" if first_seen else b"\x00"
    return Web3.keccak(packed)
