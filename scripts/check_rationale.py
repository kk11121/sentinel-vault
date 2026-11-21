#!/usr/bin/env python3
"""Numeric faithfulness check for LLM verdict rationales.

A rationale is only kept if every number in its text can be traced
to the verdict record it describes (or to a derivation the writer
declared). This is the mechanical half of the explainer's honesty
rules in docs/verdict-rationales.md: the LLM writes the words, this
script vetoes the words if the numbers do not check out.

Usage:
    check_rationale.py ENTRY.json

ENTRY.json is one rationale record (the same object that will be
appended to worker/rationales.jsonl), with fields:
    severity, score, features {name: value}, request_id, rationale,
    amount_eth, and optionally "allowed_extra": [numbers the
    writer derived from the record, e.g. the gap in hours].

Allowed numbers: the score, the severity thresholds (620, 670),
every feature value, the request id, the amount, balance_ratio
as a percent, plus allowed_extra. A number in the text passes if
it matches an allowed value within rounding tolerance (0.011
absolute or 1%).

Exit 0 = PASS (all numbers traceable), 1 = FAIL (prints offenders).
"""
import json
import re
import sys

THRESHOLDS = (620.0, 670.0)
NUMBER = re.compile(r"\d+(?:\.\d+)?")


def close(a, b):
    return abs(a - b) <= max(0.011, 0.01 * abs(b))


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    with open(sys.argv[1]) as f:
        entry = json.load(f)

    allowed = list(THRESHOLDS)
    allowed.append(float(entry["score"]))
    allowed.append(float(entry["request_id"]))
    if "amount_eth" in entry:
        allowed.append(float(entry["amount_eth"]))
    for v in entry["features"].values():
        allowed.append(float(v))
    if "balance_ratio" in entry["features"]:
        allowed.append(float(entry["features"]["balance_ratio"]) * 100.0)
    for v in entry.get("allowed_extra", entry.get("_allowed_extra", [])):
        allowed.append(float(v))

    bad = []
    for m in NUMBER.finditer(entry["rationale"]):
        x = float(m.group(0))
        if not any(close(x, a) for a in allowed):
            bad.append(m.group(0))
    if bad:
        print(f"FAIL: untraceable numbers in rationale: {bad}")
        return 1
    print("PASS: every number in the rationale traces to the record")
    return 0


if __name__ == "__main__":
    sys.exit(main())
