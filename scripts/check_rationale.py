#!/usr/bin/env python3
"""Numeric + semantic faithfulness check for LLM verdict rationales.

A rationale is only kept if every number in its text can be traced
to the verdict record it describes, exactly, at the precision the
text itself writes — and if its plain-language claims agree with
the record. This is the mechanical half of the explainer's honesty
rules in docs/verdict-rationales.md: the LLM writes the words, this
script vetoes the words if they do not check out.

Rules (tightened 2026-11-24 after an external review):
  * No tolerance band. A number written with k decimal digits must
    equal an allowed value rounded to k digits; an integer must
    match exactly at 0 digits. (The old ±1% band let a rationale
    print "626" for a real score of 590 — 626 is within 1% of the
    620 threshold — and "672" for a real 668.)
  * The allowed set is computed HERE, from the record only: the
    score, the thresholds (620, 670), every feature value, the
    request id, the amount, balance_ratio as a percent, and the
    derivations below. The writer cannot extend it: the old
    writer-declared "allowed_extra" field is abolished, and an
    entry still carrying it FAILS.
  * Derivations are computed from record fields, never declared:
    gap_hours = (ts - prev_request_ts) / 3600 and
    interval_multiple = gap_seconds / median_interval (43,200 s,
    the daily-small profile's median interval), when the entry
    carries both "ts" (ISO or epoch) and "prev_request_ts" (epoch).
  * Semantic claims are checked against the record: the severity
    word must match the score's band; "below/above the MEDIUM
    threshold"-style comparisons must be true of the score;
    first-seen claims ("a first-seen / new destination" vs "a
    known / long-known address") must agree with first_seen.
  * With --onchain, the entry's verdict is also compared against
    the VerdictPosted log of its verdict_tx on Base Sepolia:
    chain, vault, requestId, severity and score must match, and
    featuresHash is recomputed from the entry's feature vector
    (model.features.features_hash) and compared — unless the
    stored vector is rounded to <=2 decimal places, in which case
    the hash (which commits to full-precision floats) is reported
    as not recomputable from the record and the full check is
    scripts/replay.py. This needs the entry to carry "to" (the
    request's destination). Exit 2 means UNVERIFIABLE (missing
    fields or RPC failure), not a pass.

Usage:
    check_rationale.py ENTRY.json [--onchain]

ENTRY.json is one rationale record (the same object that will be
appended to worker/rationales.jsonl).

Exit 0 = PASS, 1 = FAIL (prints every reason), 2 = UNVERIFIABLE.
"""
import json
import re
import sys
from datetime import datetime

THRESHOLDS = {"MEDIUM": 620.0, "HIGH": 670.0}
MEDIAN_INTERVAL_SECONDS = 43200.0  # PROFILES["daily-small"]
NUMBER = re.compile(r"\d+(?:\.\d+)?")
FEATURE_ORDER = [
    "amount_ratio", "first_seen", "interval_log", "count_1h",
    "sum_1h_ratio", "balance_ratio", "count_24h", "sum_24h_ratio",
]
SEVERITY_BY_SCORE = lambda s: "LOW" if s < 620 else ("MEDIUM" if s < 670 else "HIGH")
SEVERITY_TO_INT = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}


def parse_ts(entry):
    ts = entry.get("ts_epoch", entry.get("ts"))
    if ts is None:
        return None
    if isinstance(ts, (int, float)):
        return float(ts)
    try:
        return datetime.fromisoformat(str(ts)).timestamp()
    except ValueError:
        return None


def allowed_values(entry):
    allowed = list(THRESHOLDS.values())
    allowed.append(float(entry["score"]))
    allowed.append(float(entry["request_id"]))
    if "amount_eth" in entry:
        allowed.append(float(entry["amount_eth"]))
    for v in entry["features"].values():
        allowed.append(float(v))
    if "balance_ratio" in entry["features"]:
        allowed.append(float(entry["features"]["balance_ratio"]) * 100.0)
    ts = parse_ts(entry)
    prev = entry.get("prev_request_ts")
    if ts is not None and prev is not None:
        gap_seconds = ts - float(prev)
        allowed.append(gap_seconds / 3600.0)               # gap_hours
        allowed.append(gap_seconds / MEDIAN_INTERVAL_SECONDS)  # interval_multiple
    return allowed


def matches(token, allowed):
    k = len(token.split(".")[1]) if "." in token else 0
    x = float(token)
    return any(abs(round(a, k) - x) < 1e-9 for a in allowed)


def semantic_failures(entry):
    fails = []
    text = entry["rationale"]
    score = float(entry["score"])
    severity = entry["severity"]

    # The record itself must be internally consistent.
    if SEVERITY_BY_SCORE(score) != severity:
        fails.append(f"severity {severity} contradicts score {entry['score']} "
                     f"(band is {SEVERITY_BY_SCORE(score)})")

    # A severity the text names for this verdict must be the record's.
    for m in re.finditer(r"scored\s+(LOW|MEDIUM|HIGH)", text):
        if m.group(1) != severity:
            fails.append(f"text says 'scored {m.group(1)}', record is {severity}")
    for m in re.finditer(r"\((LOW|MEDIUM|HIGH)\)", text):
        if m.group(1) != severity:
            fails.append(f"text labels the verdict ({m.group(1)}), record is {severity}")

    # Threshold comparisons must be true of the score.
    def bound(name, num):
        return float(num) if num else THRESHOLDS[name]

    for m in re.finditer(
            r"(below|under|beneath)\s+(?:the\s+)?(MEDIUM|HIGH)\s+threshold"
            r"(?:\s+of\s+(\d+(?:\.\d+)?))?", text, re.I):
        b = bound(m.group(2).upper(), m.group(3))
        if not score < b:
            fails.append(f"text claims score is below {b:g}, score is {entry['score']}")
    for m in re.finditer(
            r"(above|over)\s+(?:the\s+)?(MEDIUM|HIGH)\s+threshold"
            r"(?:\s+of\s+(\d+(?:\.\d+)?))?", text, re.I):
        b = bound(m.group(2).upper(), m.group(3))
        if not score > b:
            fails.append(f"text claims score is above {b:g}, score is {entry['score']}")
    for m in re.finditer(
            r"(exceeds?)\s+(?:the\s+)?(MEDIUM|HIGH)\s+threshold"
            r"(?:\s+of\s+(\d+(?:\.\d+)?))?", text, re.I):
        b = bound(m.group(2).upper(), m.group(3))
        if not score > b:
            fails.append(f"text claims score exceeds {b:g}, score is {entry['score']}")
    for m in re.finditer(r"(below|under|beneath)\s+(\d{3,}(?:\.\d+)?)", text, re.I):
        if not score < float(m.group(2)):
            fails.append(f"text claims score is below {m.group(2)}, score is {entry['score']}")
    for m in re.finditer(r"(above|over|exceeds?)\s+(\d{3,}(?:\.\d+)?)", text, re.I):
        if not score > float(m.group(2)):
            fails.append(f"text claims score is above {m.group(2)}, score is {entry['score']}")
    for m in re.finditer(r"(\d{3,}(?:\.\d+)?)\s*未満", text):
        if not score < float(m.group(1)):
            fails.append(f"text claims score is under {m.group(1)}, score is {entry['score']}")
    for m in re.finditer(r"(\d{3,}(?:\.\d+)?)\s*を超", text):
        if not score > float(m.group(1)):
            fails.append(f"text claims score exceeds {m.group(1)}, score is {entry['score']}")

    # first_seen claims must agree with the feature (citations stripped
    # first, so "first_seen 0.0" is not mistaken for a claim).
    if "first_seen" in entry["features"]:
        fs = float(entry["features"]["first_seen"])
        stripped = re.sub(r"first_seen\s+\d+(?:\.\d+)?", "", text)
        new_claims = [
            r"first[- ]seen", r"new destination", r"never (?:been )?(?:seen|observed)",
            r"previously unseen", r"unseen destination", "初見",
        ]
        known_claims = [
            r"known (?:address|destination)", r"long-known", r"seen before",
            r"not (?:a )?new",
        ]
        if any(re.search(p, stripped, re.I) for p in new_claims) and fs != 1.0:
            fails.append(f"text claims a first-seen/new destination, first_seen is {fs:g}")
        if any(re.search(p, stripped, re.I) for p in known_claims) and fs != 0.0:
            fails.append(f"text claims a known destination, first_seen is {fs:g}")
    return fails


def onchain_check(entry):
    """Return (status, message): status in verified/mismatch/unverifiable."""
    if "to" not in entry or "verdict_tx" not in entry:
        return "unverifiable", "entry lacks 'to' or 'verdict_tx'"
    try:
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from web3 import Web3
        from model.features import features_hash
        with open(os.path.join(os.path.dirname(__file__), "..", "deployments.json")) as f:
            registry = json.load(f)["registry"]
        w3 = Web3(Web3.HTTPProvider("https://sepolia.base.org",
                                    request_kwargs={"timeout": 30}))
        receipt = w3.eth.get_transaction_receipt(entry["verdict_tx"])
        topic0 = Web3.keccak(
            text="VerdictPosted(uint256,address,uint256,uint8,uint256,bytes32,bytes32)")
        log = next((l for l in receipt["logs"]
                    if l["address"].lower() == registry.lower()
                    and l["topics"][0] == topic0), None)
        if log is None:
            return "mismatch", "no VerdictPosted log from the registry in verdict_tx"
        chain_id = int.from_bytes(log["topics"][1], "big")
        vault = "0x" + log["topics"][2].hex()[-40:]
        request_id = int.from_bytes(log["topics"][3], "big")
        data = log["data"]
        if isinstance(data, str):
            data = bytes.fromhex(data[2:])
        severity_i = int.from_bytes(data[0:32], "big")
        score_i = int.from_bytes(data[32:64], "big")
        chain_hash = "0x" + data[64:96].hex()
        problems = []
        if chain_id != int(entry["chain"]):
            problems.append(f"chain {chain_id} != entry {entry['chain']}")
        if vault.lower() != str(entry["vault"]).lower():
            problems.append(f"vault {vault} != entry {entry['vault']}")
        if request_id != int(entry["request_id"]):
            problems.append(f"requestId {request_id} != entry {entry['request_id']}")
        if severity_i != SEVERITY_TO_INT[entry["severity"]]:
            problems.append(f"severity {severity_i} != entry {entry['severity']}")
        if score_i != int(entry["score"]):
            problems.append(f"score {score_i} != entry {entry['score']}")
        feats = [float(entry["features"][name]) for name in FEATURE_ORDER]
        amount_wei = int(round(float(entry["amount_eth"]) * 10**18))
        recomputed = "0x" + features_hash(
            feats, amount_wei, entry["to"], feats[1] > 0.5).hex()
        hash_note = ""
        if recomputed.lower() != chain_hash.lower():
            # The on-chain hash commits to the worker's full-precision
            # floats. A stored vector rounded to <=2 decimal places
            # (the worker log's rendering, used by entries up to
            # 2026-11-24) can never reproduce it — that is a property
            # of the record, not evidence of a wrong verdict, and the
            # full check for such entries is scripts/replay.py, which
            # recomputes the features from chain data. A vector stored
            # at full precision that fails to reproduce the hash IS a
            # mismatch.
            def decimals(v):
                r = repr(float(v))
                return len(r.split(".")[1]) if "." in r else 0
            if all(decimals(entry["features"][n]) <= 2 for n in FEATURE_ORDER):
                hash_note = ("; featuresHash not recomputable from the stored "
                             "vector (rounded to 2dp) — use scripts/replay.py")
            else:
                problems.append(f"featuresHash {chain_hash} != recomputed {recomputed}")
        if problems:
            return "mismatch", "; ".join(problems)
        return "verified", ("chain, vault, requestId, severity and score match "
                            "the VerdictPosted log" + hash_note)
    except Exception as e:  # RPC failure, pruned history, missing web3…
        return "unverifiable", f"{type(e).__name__}: {e}"


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 1:
        print(__doc__)
        return 2
    with open(args[0]) as f:
        entry = json.load(f)

    fails = []
    if "allowed_extra" in entry or "_allowed_extra" in entry:
        fails.append("entry carries a writer-declared allowed_extra — abolished; "
                     "derivations are computed from the record by this script")
    if entry.get("rationale"):
        allowed = allowed_values(entry)
        bad = [m.group(0) for m in NUMBER.finditer(entry["rationale"])
               if not matches(m.group(0), allowed)]
        if bad:
            fails.append(f"untraceable or inexact numbers in rationale: {bad}")
        fails.extend(semantic_failures(entry))

    if "--onchain" in sys.argv:
        status, msg = onchain_check(entry)
        print(f"ONCHAIN {status.upper()}: {msg}")
        if status == "mismatch":
            fails.append(f"on-chain mismatch: {msg}")
        elif status == "unverifiable":
            if fails:
                print(f"FAIL: {'; '.join(fails)}")
                return 1
            return 2
    if fails:
        print(f"FAIL: {'; '.join(fails)}")
        return 1
    print("PASS: every number traces exactly to the record and every claim agrees with it")
    return 0


if __name__ == "__main__":
    sys.exit(main())
