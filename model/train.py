"""Train the one-class Isolation Forest on synthetic normal behaviour
and export it as JSON (model/model.json). The model file's keccak256 is
the modelHash posted on-chain with every verdict."""
import json
import os
import sys

import numpy as np
from sklearn.ensemble import IsolationForest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from features import FEATURE_NAMES, compute_features  # noqa: E402
from gen_data import gen_history  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
N_ESTIMATORS = 100
MAX_SAMPLES = 128
RANDOM_STATE = 42


def build_training_rows():
    rows, meta = [], {}
    # daily-small: 180 days; monthly-large: 5 years (thin rate)
    for name, days, seed in (("daily-small", 180, 42), ("monthly-large", 1825, 43)):
        profile, history, balances = gen_history(name, days=days, seed=seed)
        for i, h in enumerate(history):
            rows.append(compute_features(profile, history[:i], h[1], h[2], h[0], balances[i]))
        meta[name] = len(history)
    return np.array(rows), meta


def export_tree(estimator):
    tree = estimator.tree_
    return {
        "children_left": [int(v) for v in tree.children_left],
        "children_right": [int(v) for v in tree.children_right],
        "feature": [int(v) for v in tree.feature],
        "threshold": [round(float(v), 6) for v in tree.threshold],
        "leaf_size": [int(v) for v in tree.n_node_samples],
    }


def main():
    X, meta = build_training_rows()
    clf = IsolationForest(
        n_estimators=N_ESTIMATORS,
        max_samples=min(MAX_SAMPLES, len(X)),
        random_state=RANDOM_STATE,
    )
    clf.fit(X)

    data = {
        "version": "iforest-1",
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
        },
    }
    out = os.path.join(HERE, "model.json")
    with open(out, "w") as f:
        json.dump(data, f, separators=(",", ":"))

    # Calibrate thresholds with the pure-python scorer on training data:
    # MEDIUM = 97.5th pct of normal scores, HIGH = 99.5th pct.
    from scorer import Model

    model = Model.load(out)
    scores = sorted(model.score1000(list(x)) for x in X)
    n = len(scores)
    data["thresholds"] = {
        "medium": scores[min(n - 1, int(0.975 * n))],
        "high": scores[min(n - 1, int(0.995 * n))],
    }
    with open(out, "w") as f:
        json.dump(data, f, separators=(",", ":"))

    from scorer import model_hash

    print(f"rows={len(X)} per_personality={meta}")
    print(f"thresholds: MEDIUM>={data['thresholds']['medium']} HIGH>={data['thresholds']['high']}")
    print(f"model.json: {os.path.getsize(out)} bytes")
    print(f"modelHash: {model_hash(out).hex()}")


if __name__ == "__main__":
    main()
