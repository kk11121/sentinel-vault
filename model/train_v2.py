"""Train model v2: same Isolation Forest recipe as v1, but the training
data comes from generator v2 (which includes rare large payments to
known destinations), and the severity thresholds are calibrated on a
DEDICATED calibration set (seed 1234) instead of the training scores —
v1's thresholds were training percentiles, which understated the tail
of held-out normal traffic (6 of 236 held-out normals scored HIGH).

Exports model/model_v2.json. Adoption is decided by eval/run_eval.py's
v1-vs-v2 comparison under the criteria recorded in eval/RESULTS.md;
this script only trains.
"""
import json
import os
import sys

import numpy as np
from sklearn.ensemble import IsolationForest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from features import FEATURE_NAMES, compute_features  # noqa: E402
from gen_data import gen_history  # noqa: E402
from train import N_ESTIMATORS, MAX_SAMPLES, RANDOM_STATE, export_tree  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
CAL_SEED = 1234


def rows_for(name, days, seed):
    profile, history, balances = gen_history(name, days=days, seed=seed, large_known=True)
    return [
        compute_features(profile, history[:i], h[1], h[2], h[0], balances[i])
        for i, h in enumerate(history)
    ]


def build_training_rows():
    rows, meta = [], {}
    for name, days, seed in (("daily-small", 180, 42), ("monthly-large", 1825, 43)):
        r = rows_for(name, days, seed)
        rows.extend(r)
        meta[name] = len(r)
    return np.array(rows), meta


def build_calibration_rows():
    rows = []
    for name, days in (("daily-small", 180), ("monthly-large", 1825)):
        rows.extend(rows_for(name, days, CAL_SEED))
    return rows


def main():
    X, meta = build_training_rows()
    clf = IsolationForest(
        n_estimators=N_ESTIMATORS,
        max_samples=min(MAX_SAMPLES, len(X)),
        random_state=RANDOM_STATE,
    )
    clf.fit(X)

    data = {
        "version": "iforest-2",
        "feature_names": FEATURE_NAMES,
        "max_samples": int(min(MAX_SAMPLES, len(X))),
        "thresholds": {"medium": 0, "high": 0},  # filled below
        "trees": [export_tree(e) for e in clf.estimators_],
        "train_meta": {
            "rows": int(len(X)),
            "per_personality": meta,
            "n_estimators": N_ESTIMATORS,
            "random_state": RANDOM_STATE,
            "sklearn": "IsolationForest",
            "generator": "v2 (large_known=True)",
            "calibration": f"separate set, seed {CAL_SEED}, generator v2",
        },
    }
    out = os.path.join(HERE, "model_v2.json")
    with open(out, "w") as f:
        json.dump(data, f, separators=(",", ":"))

    from scorer import Model, model_hash

    model = Model.load(out)
    cal_scores = sorted(model.score1000(x) for x in build_calibration_rows())
    n = len(cal_scores)
    data["thresholds"] = {
        "medium": cal_scores[min(n - 1, int(0.975 * n))],
        "high": cal_scores[min(n - 1, int(0.995 * n))],
    }
    with open(out, "w") as f:
        json.dump(data, f, separators=(",", ":"))

    print(f"rows={len(X)} per_personality={meta} calibration_rows={n}")
    print(f"thresholds: MEDIUM>={data['thresholds']['medium']} HIGH>={data['thresholds']['high']}")
    print(f"model_v2.json: {os.path.getsize(out)} bytes")
    print(f"modelHash: {model_hash(out).hex()}")


if __name__ == "__main__":
    main()
