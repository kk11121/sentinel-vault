"""Train model v3: generator-v2 data (as v2) but with the 8-feature
vector — f7/f8 add 24-hour pace aggregates, closing the slow-drain
blind spot the v2 evaluation exposed (a 10-minute-pace drain to an
already-known address scored LOW on every step under f1-f6, because
the 1-hour window features plateau as the window slides).

Same Isolation Forest recipe, same calibration-set method as v2.
Exports model/model_v3.json. Adoption decided by eval/run_eval.py
under criteria fixed there before running.
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
from train_v2 import rows_for, build_calibration_rows  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    rows, meta = [], {}
    for name, days, seed in (("daily-small", 180, 42), ("monthly-large", 1825, 43)):
        r = rows_for(name, days, seed)
        rows.extend(r)
        meta[name] = len(r)
    X = np.array(rows)

    clf = IsolationForest(
        n_estimators=N_ESTIMATORS,
        max_samples=min(MAX_SAMPLES, len(X)),
        random_state=RANDOM_STATE,
    )
    clf.fit(X)

    data = {
        "version": "iforest-3",
        "feature_names": FEATURE_NAMES,
        "max_samples": int(min(MAX_SAMPLES, len(X))),
        "thresholds": {"medium": 0, "high": 0},
        "trees": [export_tree(e) for e in clf.estimators_],
        "train_meta": {
            "rows": int(len(X)),
            "per_personality": meta,
            "n_estimators": N_ESTIMATORS,
            "random_state": RANDOM_STATE,
            "sklearn": "IsolationForest",
            "generator": "v2 (large_known=True)",
            "features": "8 (f7/f8 = 24h pace aggregates)",
            "calibration": "separate set, seed 1234, generator v2",
        },
    }
    out = os.path.join(HERE, "model_v3.json")
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
    print(f"model_v3.json: {os.path.getsize(out)} bytes")
    print(f"modelHash: {model_hash(out).hex()}")


if __name__ == "__main__":
    main()
