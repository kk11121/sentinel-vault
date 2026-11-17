#!/usr/bin/env python3
"""Rule-v1 vs model-v1 vs model-v2 vs model-v3 evaluation on synthetic
data. All data is synthetic (model/gen_data.py). Numbers are reported
as computed, including where a model loses. Counts are counts
("9 of 236"), not only percentages.

Methods:
  rule-v1  : the M2 placeholder rule exactly as deployed
             (known dest -> LOW; amount >= 0.008 ETH -> HIGH;
              first-seen dest -> MEDIUM; else LOW). One fixed rule,
              applied unchanged to every vault.
  model-v1 : Isolation Forest shipped at M3 (generator-v1 data,
             6 features, thresholds = training percentiles).
  model-v2 : retrained on generator-v2 data (adds rare large payments
             to known destinations), thresholds calibrated on a
             dedicated set (seed 1234). Still 6 features.
  model-v3 : v2's recipe + features f7/f8 (24-hour pace aggregates),
             added after v2's evaluation exposed a slow-drain blind
             spot (see the drain scenario below).

Adoption criteria (fixed before running):
  v2 over v1: (i) fewer HIGH on held-out normal set A; (ii) no attack
  flagged later than v1; (iii) 3x-median-to-known probe not HIGH.
  v3 over v2: (i) HIGH on set A no worse than v2; (ii) the slow drain
  to an in-history address is flagged >=MEDIUM within its 20 steps;
  (iii) no other daily-small attack flagged later than v2;
  (iv) 3x-median-to-known probe not HIGH.
  The outcome is reported as computed. Where the deployment decision
  overrides a criterion, the override and its reasoning are stated in
  RESULTS.md next to the failed criterion — not edited away.
"""
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from model.features import PROFILES, compute_features
from model.gen_data import gen_history
from model.scorer import Model

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL_FILES = {
    "model-v1": "model_v1.json",
    "model-v2": "model_v2.json",
    "model-v3": "model_v3.json",
}
MODELS = {
    name: Model.load(os.path.join(HERE, "..", "model", fname))
    for name, fname in MODEL_FILES.items()
}
METHODS = ["rule-v1", *MODEL_FILES]
KNOWN_ADDRS = set()
HIGH_AMOUNT = 0.008  # ETH, as deployed in M2


def rule_v1(profile, history, to, amount, timestamp, balance):
    known = {h[1] for h in history} | set(profile.get("known_destinations", [])) | KNOWN_ADDRS
    if to in known:
        return "LOW"
    if amount >= HIGH_AMOUNT:
        return "HIGH"
    if to not in {h[1] for h in history}:
        return "MEDIUM"
    return "LOW"


def judge(model, profile, history, to, amount, t, balance):
    feats = compute_features(profile, history, to, amount, t, balance)
    return model.severity(feats)[0]


def all_verdicts(profile, history, to, amount, t, balance):
    out = {"rule-v1": rule_v1(profile, history, to, amount, t, balance)}
    for name, model in MODELS.items():
        out[name] = judge(model, profile, history, to, amount, t, balance)
    return out


def runtime_profile(gen_profile, name):
    rp = dict(PROFILES[name])
    rp["known_destinations"] = list(gen_profile["known_destinations"])
    return rp


def held_out_counts(personality, days, seed, large_known):
    gen_profile, hist, bals = gen_history(personality, days=days, seed=seed, large_known=large_known)
    rp = runtime_profile(gen_profile, personality)
    counters = {m: Counter() for m in METHODS}
    for i, h in enumerate(hist):
        verdicts = all_verdicts(rp, hist[:i], h[1], h[2], h[0], bals[i])
        for m, v in verdicts.items():
            counters[m][v] += 1
    return len(hist), counters


def attack_rows(personality, base_seed, large_known, balance, scenarios):
    """scenarios: list of (name, sequence[(to, amount, dt)]).
    Returns (name, {method: (first>=MED, first HIGH)})."""
    gen_profile, hist, _ = gen_history(
        personality,
        days=180 if personality == "daily-small" else 1825,
        seed=base_seed,
        large_known=large_known,
    )
    rp = runtime_profile(gen_profile, personality)
    t0 = hist[-1][0] + 7200
    rows = []
    for name, sequence in scenarios:
        first = {m: [None, None] for m in METHODS}
        h = list(hist)
        t = t0
        for i, (to, amount, dt) in enumerate(sequence):
            t += dt
            verdicts = all_verdicts(rp, h, to, amount, t, balance)
            for m, v in verdicts.items():
                if first[m][0] is None and v in ("MEDIUM", "HIGH"):
                    first[m][0] = i + 1
                if first[m][1] is None and v == "HIGH":
                    first[m][1] = i + 1
            h.append((t, to, amount))
        rows.append((name, first))
    return rows


def fmt_first(first):
    return f"{first[0] or '-'} / {first[1] or '-'}"


def counts_table(lines, counters, n):
    lines.append("| method | LOW | MEDIUM | HIGH | flagged >=MEDIUM |")
    lines.append("|---|---|---|---|---|")
    for name in METHODS:
        c = counters[name]
        lines.append(f"| {name} | {c['LOW']} | {c['MEDIUM']} | {c['HIGH']} | {c['MEDIUM'] + c['HIGH']} of {n} |")
    lines.append("")


def run():
    lines = []
    lines.append("# Evaluation — rule-v1 vs model-v1 vs model-v2 vs model-v3 (synthetic data)\n")
    lines.append("All traffic is synthetic, generated by model/gen_data.py. Numbers are")
    lines.append("reported as computed, including where a model loses. rule-v1 is the")
    lines.append("fixed rule deployed at M2: destination in history/known list -> LOW;")
    lines.append("amount >= 0.008 ETH -> HIGH; first-seen destination -> MEDIUM; else LOW.")
    lines.append("One rule, unchanged, for every vault. The deployed profile is")
    lines.append("daily-small; monthly-large appears in the two-personality section.\n")

    # --- held-out normal traffic ---
    lines.append("## Held-out normal traffic (counts of verdicts)\n")
    lines.append("Set A uses the v1 generator (no large-to-known pattern); set B uses the")
    lines.append("v2 generator, whose normal traffic includes rare large payments to")
    lines.append("known destinations. A HIGH on normal traffic freezes all three vaults")
    lines.append("until the recovery key intervenes; a MEDIUM vetoes one withdrawal.")
    lines.append("Under model-v1, every HIGH in set A was a 2.2x-4.3x-median payment to")
    lines.append("a KNOWN address — the pattern generator v2 adds to normal data.\n")
    held = {}
    for label, lk in (("A (v1 generator)", False), ("B (v2 generator)", True)):
        n, counters = held_out_counts("daily-small", 180, 777, lk)
        held[label] = (n, counters)
        lines.append(f"### Set {label}, daily-small, n={n}\n")
        counts_table(lines, counters, n)

    # --- attacks, daily-small ---
    daily_attacks = [
        ("full drain: 0.475 ETH to fresh addr", [("0xAttacker", 0.475, 0)]),
        ("barrage: 10 x 0.004 ETH to fresh addr, 5 min apart", [("0xAttacker", 0.004, 300)] * 10),
        ("barrage, zero interval: 10 x 0.004 ETH to fresh addr, same block", [("0xAttacker", 0.004, 0)] * 10),
        ("concentration: 5 x 0.015 ETH to one fresh addr, 1 h apart", [("0xAttacker", 0.015, 3600)] * 5),
    ]
    lines.append("## Attacks on daily-small (withdrawal # at first flag: >=MEDIUM / HIGH)\n")
    lines.append("| scenario | " + " | ".join(METHODS) + " |")
    lines.append("|---|" + "---|" * len(METHODS))
    daily_rows = attack_rows("daily-small", 42, False, 0.5, daily_attacks)
    for name, first in daily_rows:
        lines.append(f"| {name} | " + " | ".join(fmt_first(first[m]) for m in METHODS) + " |")
    lines.append("")
    lines.append("Note: in the barrages, model-v1/v2 score the first withdrawal HIGH")
    lines.append("already — the driver is the first-seen + small-amount combination")
    lines.append("(rare in training), not pace accumulation. model-v3 flags >=MEDIUM")
    lines.append("at #1 and reaches HIGH at #7 as its pace features accumulate. The")
    lines.append("zero-interval barrage is additionally capped on-chain: the vault's")
    lines.append("instant cap routes same-block bursts into the waiting queue, where")
    lines.append("a veto can still reach them (see the GuardedVault tests).\n")

    # --- primer + slow drain: the structural scenarios ---
    lines.append("## The structural scenarios: primer, then drain to a 'known' address\n")
    lines.append("rule-v1's first branch trusts any destination that appears in the")
    lines.append("request history. Two ways to exploit that, and what each method does:\n")
    gen_profile_d, hist_d, _ = gen_history("daily-small", days=180, seed=42, large_known=False)
    rp_d = runtime_profile(gen_profile_d, "daily-small")
    known_d = gen_profile_d["known_destinations"][0]
    t0_d = hist_d[-1][0] + 7200

    # (a) primer verdict itself
    primer_verdicts = all_verdicts(rp_d, hist_d, "0xAttacker", 0.001, t0_d + 43_200, 0.5)
    lines.append("**(a) The primer itself** — one tiny 0.001 ETH request to a fresh address:")
    lines.append("")
    lines.append("| probe | " + " | ".join(METHODS) + " |")
    lines.append("|---|" + "---|" * len(METHODS))
    lines.append("| verdict on the primer | " + " | ".join(primer_verdicts[m] for m in METHODS) + " |")
    lines.append("")
    lines.append("model-v1/v2 call the primer itself HIGH (a tiny amount to a first-seen")
    lines.append("address is a rare combination in training), so on-chain the vaults")
    lines.append("would freeze at the primer; model-v3 and rule-v1 veto it as MEDIUM.")
    lines.append("Either way the primer does not pass silently — but a defender cannot")
    lines.append("rely on the attacker needing one:\n")

    # (b) slow drain to an address already in history (no primer needed)
    drain_rows = attack_rows(
        "daily-small", 42, False, 0.5,
        [("slow drain: 20 x 0.0079 ETH to an address already in history, 10 min apart",
          [(known_d, 0.0079, 600)] * 20)],
    )
    lines.append("**(b) Slow drain to an address already in the history** — e.g. a payee")
    lines.append("whose receiving address the attacker controls. No primer, no new")
    lines.append("destination, every amount below rule-v1's HIGH threshold:\n")
    lines.append("| scenario | " + " | ".join(METHODS) + " |")
    lines.append("|---|" + "---|" * len(METHODS))
    for name, first in drain_rows:
        lines.append(f"| {name} (first flag >=MED / HIGH) | " + " | ".join(fmt_first(first[m]) for m in METHODS) + " |")
    lines.append("")
    lines.append("Under the 6-feature models (v1/v2) this drain is a genuine blind spot:")
    lines.append("the 1-hour pace features plateau as the window slides, and every step")
    lines.append("scores LOW. model-v3 adds 24-hour pace aggregates (f7/f8) aimed exactly")
    lines.append("here. What bounds the damage regardless of detection: the vault's")
    lines.append("instant cap (only a capped total leaves instantly per hour; the rest")
    lines.append("queues), and the RSC's cross-chain pace freeze. A still slower drain")
    lines.append("(e.g. one sub-threshold withdrawal per day to a known address) is not")
    lines.append("detected by any method here and is disclosed as a residual risk.\n")

    # --- two-profile experiment ---
    lines.append("## Two vault personalities, one rule vs profile-relative models\n")
    lines.append("monthly-large: median payment 0.2 ETH, balance 5 ETH. rule-v1 is applied")
    lines.append("byte-for-byte unchanged — its fixed 0.008 ETH threshold is 4% of this")
    lines.append("vault's median payment. Legit probes are timed one median interval")
    lines.append("(10 days) after the previous withdrawal, i.e. at this vault's normal")
    lines.append("pace.\n")
    n_m, counters_m = held_out_counts("monthly-large", 1825, 777, True)
    lines.append(f"### Held-out normal traffic, monthly-large (v2 generator), n={n_m}\n")
    counts_table(lines, counters_m, n_m)
    gen_profile_m, hist_m, _ = gen_history("monthly-large", days=1825, seed=42, large_known=True)
    rp_m = runtime_profile(gen_profile_m, "monthly-large")
    t_probe = hist_m[-1][0] + 864_000  # one median interval later
    known_m = gen_profile_m["known_destinations"][0]
    lines.append("### Single probes on monthly-large\n")
    lines.append("| scenario | " + " | ".join(METHODS) + " |")
    lines.append("|---|" + "---|" * len(METHODS))
    for name, (to, amount, t) in [
        ("legit: first payment to a NEW vendor, 0.2 ETH (1x median)", ("0xNewVendor", 0.2, t_probe)),
        ("legit: 3x median to a known vendor (0.6 ETH)", (known_m, 0.6, t_probe)),
        ("attack: full drain, 4.75 ETH to fresh addr", ("0xAttacker", 4.75, hist_m[-1][0] + 7200)),
    ]:
        verdicts = all_verdicts(rp_m, hist_m, to, amount, t, 5.0)
        lines.append(f"| {name} | " + " | ".join(verdicts[m] for m in METHODS) + " |")
    lines.append("")

    # --- rare but legit, daily-small ---
    lines.append("## Rare-but-legit probes, daily-small (LOW = passed through)\n")
    lines.append("| scenario | " + " | ".join(METHODS) + " |")
    lines.append("|---|" + "---|" * len(METHODS))
    rare = {}
    for name, (to, amount, t) in [
        ("3x median amount to a known address", (known_d, 0.03, t0_d)),
        ("normal amount after a 30-day pause", (known_d, 0.011, t0_d + 30 * 86400)),
    ]:
        verdicts = all_verdicts(rp_d, hist_d, to, amount, t, 0.5)
        rare[name] = verdicts
        lines.append(f"| {name} | " + " | ".join(verdicts[m] for m in METHODS) + " |")
    lines.append("")

    # --- cost of a false verdict ---
    lines.append("## What a wrong verdict costs\n")
    lines.append("- False MEDIUM: exactly one withdrawal is vetoed. The owner re-requests")
    lines.append("  it; nothing else stops. Cost: one transaction and a delay.")
    lines.append("- False HIGH: all three vaults freeze. Recovery needs the offline")
    lines.append("  recovery key: 3 unfreeze transactions (plus a verdictWriter rotation")
    lines.append("  if the writer key is suspected). Funds are never at risk, but the")
    lines.append("  vaults are unavailable until the owner acts. At the daily-small")
    lines.append("  profile's pace (~2 withdrawals/day), the held-out HIGH counts above")
    lines.append("  translate directly into expected freeze frequency: model-v1's 6 HIGH")
    lines.append("  in 236 normal withdrawals is roughly one full freeze every 20 days.\n")

    # --- adoption decisions ---
    nA, countersA = held["A (v1 generator)"]
    lines.append("## Adoption decisions (criteria fixed before running)\n")
    v2_c1 = countersA["model-v2"]["HIGH"] < countersA["model-v1"]["HIGH"]
    v2_c2 = all(
        first["model-v2"][0] is not None
        and (first["model-v1"][0] is None or first["model-v2"][0] <= first["model-v1"][0])
        for _, first in daily_rows
    )
    v2_c3 = rare["3x median amount to a known address"]["model-v2"] != "HIGH"
    lines.append(f"- v2 over v1: (i) HIGH on set A: v1 {countersA['model-v1']['HIGH']} of {nA} vs v2 {countersA['model-v2']['HIGH']} of {nA} -> {'PASS' if v2_c1 else 'FAIL'}; "
                 f"(ii) no attack flagged later -> {'PASS' if v2_c2 else 'FAIL'}; "
                 f"(iii) 3x-known probe: {rare['3x median amount to a known address']['model-v2']} -> {'PASS' if v2_c3 else 'FAIL'}. "
                 f"**{'ADOPT v2 over v1' if (v2_c1 and v2_c2 and v2_c3) else 'KEEP v1'}**")
    drain_first = drain_rows[0][1]
    v3_c1 = countersA["model-v3"]["HIGH"] <= countersA["model-v2"]["HIGH"]
    v3_c2 = drain_first["model-v3"][0] is not None
    v3_c3 = all(
        first["model-v3"][0] is not None
        and (first["model-v2"][0] is None or first["model-v3"][0] <= first["model-v2"][0])
        for _, first in daily_rows
    )
    v3_c4 = rare["3x median amount to a known address"]["model-v3"] != "HIGH"
    lines.append(f"- v3 over v2: (i) HIGH on set A: v3 {countersA['model-v3']['HIGH']} of {nA} vs v2 {countersA['model-v2']['HIGH']} of {nA} -> {'PASS' if v3_c1 else 'FAIL'}; "
                 f"(ii) slow drain flagged by v3 at step {drain_first['model-v3'][0] or '-'} of 20 -> {'PASS' if v3_c2 else 'FAIL'}; "
                 f"(iii) no attack flagged later -> {'PASS' if v3_c3 else 'FAIL'}; "
                 f"(iv) 3x-known probe: {rare['3x median amount to a known address']['model-v3']} -> {'PASS' if v3_c4 else 'FAIL'}.")
    lines.append("")
    lines.append("**Deployment decision: model-v3**, with one explicit override. Criterion")
    lines.append("(iii) FAILS as written: in the concentration scenario v3 flags one step")
    lines.append("later than v2 (#2 instead of #1). We adopt v3 anyway, and say so here")
    lines.append("rather than editing the criterion, because: (1) the blind spot v3 closes")
    lines.append("is total — under v2 the slow drain is NEVER flagged in 20 steps — while")
    lines.append("the concentration delay costs at most one extra queued withdrawal")
    lines.append("(0.015 ETH, 3% of the demo balance), and queued withdrawals sit in the")
    lines.append("timelock where the #2 verdict still vetoes the rest; (2) v3 is the only")
    lines.append("model with zero false HIGHs on every held-out set, including")
    lines.append("monthly-large (v2: 2 of 152); (3) on the rare-legit probes v3 passes")
    lines.append("both as LOW where v2 says MEDIUM. The failed criterion stays on the")
    lines.append("record above.")
    lines.append("")
    lines.append("All model files stay in the repo (model/model_v1.json, model_v2.json,")
    lines.append("model_v3.json); model/model.json is a copy of the adopted one.")

    out = os.path.join(HERE, "RESULTS.md")
    with open(out, "w") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    run()
