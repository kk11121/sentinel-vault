"""Pure-python scorer for the exported Isolation Forest (model.json).

No sklearn, no pickle: the forest is plain JSON (tree arrays), so the
worker, the replay tool and any auditor run exactly the same model.
Score convention: score1000 in (0, 1000], higher = more anomalous,
score1000 = 1000 * 2 ** (-E[path] / c(max_samples)).
"""
import json
import math
import os

EULER_GAMMA = 0.5772156649015329


def _c(n):
    """Average path length of an unsuccessful BST search (sklearn's
    _average_path_length)."""
    if n <= 1:
        return 0.0
    if n == 2:
        return 1.0
    return 2.0 * (math.log(n - 1) + EULER_GAMMA) - 2.0 * (n - 1) / n


class Model:
    def __init__(self, data):
        self.data = data
        self.max_samples = data["max_samples"]
        self.trees = data["trees"]
        self.thresholds = data["thresholds"]
        self._c_max = _c(self.max_samples)

    @classmethod
    def load(cls, path=None):
        if path is None:
            path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "model.json")
        with open(path) as f:
            return cls(json.load(f))

    def _path_length(self, tree, x):
        cl, cr = tree["children_left"], tree["children_right"]
        feat, thr = tree["feature"], tree["threshold"]
        leaf_size = tree["leaf_size"]
        node, depth = 0, 0
        while cl[node] != -1:
            node = cr[node] if x[feat[node]] > thr[node] else cl[node]
            depth += 1
        return depth + _c(leaf_size[node])

    def score1000(self, features):
        mean_path = sum(self._path_length(t, features) for t in self.trees) / len(self.trees)
        return int(round(1000 * 2 ** (-mean_path / self._c_max)))

    def severity(self, features):
        s = self.score1000(features)
        if s >= self.thresholds["high"]:
            return "HIGH", s
        if s >= self.thresholds["medium"]:
            return "MEDIUM", s
        return "LOW", s


def model_hash(path=None):
    from web3 import Web3

    if path is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "model.json")
    with open(path, "rb") as f:
        return Web3.keccak(f.read())
