#!/usr/bin/env python3
"""Synthesize per-scene English narration for the v6 demo video (TTS)."""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "narration_v6")
os.makedirs(OUT, exist_ok=True)

SCENES = [
    "Sentinel Vault. When a treasury's hot key is stolen, the first bad withdrawal on one chain should freeze the vaults on all the others. An off-chain model decides. A Reactive contract enforces.",
    "Large withdrawals wait in a timelock queue, and small ones are capped per hour. The model judges every request and posts its verdict on-chain. The Reactive contract vetoes, freezes — and watches the request pace itself.",
    "First, the attacks that must fail. A withdrawal request from a non-owner reverts. The daily key cannot unfreeze its own vault. A stranger cannot cancel a queued withdrawal. And a verdict naming a vault the Reactive contract does not watch is simply ignored.",
    "A normal withdrawal to a known address. The Reactive contract logs the request, the model scores it low in eleven seconds, and it executes after the queue wait. A silent A I never blocks funds.",
    "On Ethereum Sepolia, a medium verdict vetoes exactly one withdrawal — nothing else freezes. When a second medium lands within the hour, the Reactive contract escalates on its own: veto, plus a freeze of all three vaults.",
    "A first-seen destination scores high. One verdict vetoes the flagged request and freezes the vaults on all three chains. And even after a recovery unfreeze, the flagged request itself stays dead.",
    "Now the worker is deliberately stopped. The eleventh request within an hour makes the Reactive contract freeze everything by itself. No A I verdict is involved.",
    "Every verdict carries the feature hash and the model hash. This replay, recomputed from chain data, matches on all four fields. It also works from a clean clone, with no keys present.",
    "Why A I at all? A slow drain to a known address slips past a fixed rule forever. The current model flags it at step two. And its false-alarm cost is published, not hidden.",
    "Sentinel Vault. The model decides, the Reactive contract enforces, and the model's key can move nothing. Testnet only. Thank you for watching.",
]


def main():
    only = [int(x) for x in sys.argv[1:]] or range(1, len(SCENES) + 1)
    for i in only:
        out = os.path.join(OUT, f"scene{i:02d}.mp3")
        r = subprocess.run(
            ["/opt/hatch/bin/tts", "speak", "--text", SCENES[i - 1],
             "--language", "en", "--output", out],
            capture_output=True, text=True)
        print(i, "ok" if r.returncode == 0 else f"FAIL {r.stderr[-200:]}",
              os.path.getsize(out) if os.path.exists(out) else 0)


if __name__ == "__main__":
    main()
