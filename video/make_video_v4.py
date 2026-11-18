#!/usr/bin/env python3
"""Sentinel Vault demo video v4 — narrated, animated, with real
explorer screenshots.

All data (tx hashes, scores, timings) is from the real 2026-11-18
evidence run in docs/deployments.md. The explorer cards are rendered
from data read live from the explorers themselves (Blockscout API for
Base/Sepolia; the Reactscan tx page for Lasna) on 2026-11-18 —
Basescan's own pages were behind a Cloudflare bot wall for our
browser, so its data was taken from the mirror explorer instead.
Narration: video/narration/sceneNN.mp3 (TTS, see narration.py).
Output: video/demo.mp4 (1280x720, English narration + burned-in
captions). Supersedes make_video_v3.py (silent slides).
"""
import os
import subprocess

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FRAMES = os.path.join(HERE, "frames_v4")
SHOTS = os.path.join(HERE, "shots")
NARR = os.path.join(HERE, "narration")
os.makedirs(FRAMES, exist_ok=True)

W, H = 1280, 720
BG = (13, 17, 23)
PANEL = (22, 27, 34)
FG = (230, 237, 243)
DIM = (139, 148, 158)
GREEN = (63, 185, 80)
RED = (248, 81, 73)
AMBER = (210, 153, 34)
BLUE = (88, 166, 255)
DARKRED = (90, 30, 28)

MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
MONO_B = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
SANS_B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
SANS = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

SEGMENTS = []  # (image_path, duration_seconds)


def font(path, size):
    return ImageFont.truetype(path, size)


def wrap(draw, text, fnt, max_w):
    words, lines, cur = text.split(), [], ""
    for w_ in words:
        trial = (cur + " " + w_).strip()
        if draw.textlength(trial, font=fnt) <= max_w:
            cur = trial
        else:
            lines.append(cur)
            cur = w_
    if cur:
        lines.append(cur)
    return lines


def base_canvas(title, caption, title_color=FG):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([40, 36, W - 40, H - 130], fill=PANEL)
    d.text((70, 58), title, font=font(SANS_B, 30), fill=title_color)
    d.rectangle([0, H - 118, W, H], fill=(0, 0, 0))
    cf = font(SANS, 25)
    lines = wrap(d, caption, cf, W - 120)
    cy = H - 118 + (118 - len(lines) * 34) // 2
    for line in lines:
        d.text((60, cy), line, font=cf, fill=(255, 255, 255))
        cy += 34
    return img, d


_counter = [0]


def emit(img, duration):
    _counter[0] += 1
    path = os.path.join(FRAMES, f"s{_counter[0]:03d}.png")
    img.save(path)
    SEGMENTS.append((path, duration))
    return path


def text_scene(title, body, caption, duration, title_color=FG):
    img, d = base_canvas(title, caption, title_color)
    y = 112
    for text, color, size, bold in body:
        fnt = font(MONO_B if bold else MONO, size)
        for line in text.split("\n"):
            d.text((70, y), line, font=fnt, fill=color)
            y += int(size * 1.45)
        y += 4
    emit(img, duration)


def card_scene(title, caption, duration, source, rows):
    """Explorer-style transaction card rendered from data read live from
    the explorer (Blockscout API / Reactscan page, 2026-11-18). The
    source line names where the data came from; the same transactions
    are linked from the README."""
    img, d = base_canvas(title, caption)
    y = 118
    d.rectangle([70, y, 1210, y + 348], fill=(16, 21, 28), outline=DIM, width=1)
    ry = y + 22
    for label, value, color in rows:
        d.text((95, ry), label, font=font(MONO, 19), fill=DIM)
        if label == "Status":
            d.rectangle([330, ry - 2, 470, ry + 30], fill=(20, 60, 35))
            d.text((348, ry + 2), value, font=font(MONO_B, 19), fill=GREEN)
        else:
            d.text((330, ry), value, font=font(MONO, 19), fill=color)
        ry += 44
    d.text((70, y + 366), source, font=font(MONO, 17), fill=DIM)
    emit(img, duration)


def fade(img_a_path, img_b_path, duration=0.5, steps=5):
    a = Image.open(img_a_path).convert("RGB")
    b = Image.open(img_b_path).convert("RGB")
    for k in range(1, steps):
        blend = Image.blend(a, b, k / steps)
        emit(blend, duration / steps)


# ---------------------------------------------------------------- scenes
CAP = [
    "Sentinel Vault. An off-chain model decides; a Reactive contract enforces. The model's key can post verdicts and nothing else.",
    "Large withdrawals queue in a timelock; small ones are capped per hour. The model judges every request. The Reactive contract also guards the pace itself.",
    "First, the attacks that must fail: a non-owner's request reverts, and the daily key cannot unfreeze its own vault. Real failed transactions, on-chain.",
    "A normal withdrawal: the Reactive contract logs the request, the model scores it LOW in ten seconds, and it executes after the wait. Fail-open by design.",
    "Three rapid withdrawals trip the model. A MEDIUM verdict vetoes that one withdrawal — one second from verdict to callback.",
    "One HIGH verdict freezes the vaults on all three chains within seven seconds — before the queued withdrawal can execute.",
    "With the worker deliberately stopped, the eleventh request in an hour makes the Reactive contract freeze everything by itself.",
    "Every verdict carries feature and model hashes. The replay recomputes them from chain data — this is the real output, all four fields MATCH.",
    "Why AI at all? A slow drain to a known address slips past a fixed rule forever; the model flags it at step two. False-alarm costs are published too.",
    "Sentinel Vault: the model decides, the Reactive contract enforces, and the model's key can move nothing. Testnet only.",
]

DUR = {}  # filled from narration lengths in main()


def scene1():
    text_scene("Sentinel Vault", [
        ("When a treasury's hot key is stolen, the first bad", FG, 25, False),
        ("withdrawal on one chain should freeze the others.", FG, 25, False),
        ("", FG, 16, False),
        ("An off-chain model decides.", BLUE, 26, True),
        ("A Reactive contract enforces.", BLUE, 26, True),
        ("The model's key can post verdicts and nothing else.", FG, 24, False),
    ], CAP[0], DUR[1])


def scene2():
    text_scene("How it works", [
        ("GuardedVault x3 chains        VerdictRegistry        SentinelReactive", FG, 19, True),
        ("(Base / Eth Sepolia /         (Base Sepolia)         (Lasna, RSC)", DIM, 19, False),
        (" Unichain Sepolia)", DIM, 19, False),
        ("", FG, 14, False),
        ("  owner-only request ──► worker: 8 features, Isolation Forest", FG, 20, False),
        ("                         verdict posted on-chain ──► RSC reacts:", FG, 20, False),
        ("", FG, 14, False),
        ("  LOW ..... nothing (queued withdrawal executes, fail-open)", GREEN, 20, False),
        ("  MEDIUM .. veto that one withdrawal", AMBER, 20, False),
        ("  HIGH .... freeze ALL three vaults, pre-emptively", RED, 20, False),
        ("  RSC also watches requests: >10/hour across chains", FG, 20, False),
        ("  freezes everything by itself — no verdict needed", FG, 20, False),
    ], CAP[1], DUR[2])


def scene3():
    text_scene("First: the attacks that must fail", [
        ("$ attacker.requestWithdrawal(...)        [not the owner]", FG, 20, False),
        ("  tx 0xba697361...  status 0  FAILED — reverts NotOwner", RED, 20, True),
        ("", FG, 14, False),
        ("$ owner.unfreeze()                       [daily key, frozen vault]", FG, 20, False),
        ("  tx 0x4293eca0...  status 0  FAILED — reverts NotRecovery", RED, 20, True),
        ("", FG, 14, False),
        ("Only the offline recovery key can unfreeze or reconfigure.", FG, 20, False),
        ("The daily key cannot lift a freeze placed on itself.", FG, 20, False),
    ], CAP[2], DUR[3])


def scene4():
    """Animated timeline: request -> verdict (+7s) -> executed (+98s)."""
    steps = [
        (0.30, 1), (0.25, 2), (0.25, 3), (0.20, 4),
    ]
    events = [
        ("t+0s   request 0.008 ETH to owner  [Base]", "tx 0xcc8d2059...", FG),
        ("t+0s   RSC logs RequestSeen  [Lasna reactive tx]", "tx 0x1c5f2266...", FG),
        ("t+7s   verdict LOW (583)  [Base]", "tx 0xcdfdc918...", GREEN),
        ("t+98s  executed after the wait  [Base]", "tx 0xdb81ae9c...", GREEN),
    ]
    for frac, shown in steps:
        img, d = base_canvas("Normal withdrawal — judged LOW, executes", CAP[3])
        # timeline bar
        x0, x1, yb = 90, 1190, 150
        d.line([x0, yb, x1, yb], fill=DIM, width=4)
        pos = [0.02, 0.10, 0.45, 0.97]
        for j, p in enumerate(pos):
            x = int(x0 + (x1 - x0) * p)
            col = GREEN if j < shown else DIM
            d.ellipse([x - 9, yb - 9, x + 9, yb + 9], fill=col)
        y = 200
        for j in range(shown):
            text, sub, col = events[j]
            d.text((90, y), text, font=font(MONO_B, 21), fill=col)
            d.text((90, y + 32), sub, font=font(MONO, 17), fill=DIM)
            y += 84
        emit(img, DUR[4] * frac)
    card_scene("The verdict, as the explorer shows it", CAP[3], 6.5,
               "Data read from the Base Sepolia explorer (Blockscout API), 2026-11-18.",
               [("Tx Hash", "0xcdfdc918...1effdfbc", FG),
                ("Status", "Success", GREEN),
                ("Block", "60329273", FG),
                ("From", "0xD4bdEb62...F9B9c307  (verdictWriter)", FG),
                ("To", "0x0e55C8F8...63abB7F32  (VerdictRegistry)", FG),
                ("Action", "postVerdict — LOW, score 583", GREEN)])


def scene5():
    text_scene("Burst of withdrawals — MEDIUM vetoes one", [
        ("Three 0.003 ETH requests, seconds apart     [Base Sepolia]", FG, 20, False),
        ("  #1, #2 instant — #3 queued by the hourly instant cap", DIM, 19, False),
        ("", FG, 14, False),
        ("[worker] req 2 -> MEDIUM (662)   tx 0x65b2a6a1...", AMBER, 20, True),
        ("t+1s  RSC VetoRequested                     [Lasna]", FG, 20, False),
        ("      reactive tx 0x40411f93...", DIM, 18, False),
        ("t+1s  veto lands via callback proxy", FG, 20, False),
        ("      WithdrawalVetoed   tx 0x52726a3b...", AMBER, 20, False),
    ], CAP[4], DUR[5])


def scene6():
    """Animated freeze propagation across the three vault boxes."""
    chains = [
        ("GuardedVault — Base Sepolia", "+2s"),
        ("GuardedVault — Unichain Sepolia", "+2s"),
        ("GuardedVault — Ethereum Sepolia", "+7s"),
    ]
    phases = [0, 1, 2, 3]  # how many boxes are frozen
    weights = [0.34, 0.22, 0.22, 0.22]
    for frozen_count, wfrac in zip(phases, weights):
        img, d = base_canvas("HIGH — all three vaults freeze pre-emptively", CAP[5])
        d.text((70, 104), "[worker] req 3 -> HIGH (713)   tx 0xdafeeea7...",
               font=font(MONO_B, 20), fill=RED)
        d.text((70, 140), "RSC FreezeRequested x3   reactive tx 0x2fab0dfd...  [Lasna]",
               font=font(MONO, 18), fill=DIM)
        y = 200
        for j, (name, delta) in enumerate(chains):
            frozen = j < frozen_count
            fill = DARKRED if frozen else PANEL
            outline = RED if frozen else DIM
            d.rectangle([70, y, 1210, y + 74], fill=fill, outline=outline, width=2)
            d.text((95, y + 12), name, font=font(MONO_B, 22), fill=FG)
            status = f"frozen = true   ({delta})" if frozen else "frozen = false"
            d.text((95, y + 42), status, font=font(MONO, 19),
                   fill=RED if frozen else DIM)
            y += 92
        if frozen_count == 3:
            d.text((70, y + 6), "The HIGH verdict vetoes its own request too: tx 0x11683dd2... (WithdrawalVetoed)",
                   font=font(MONO, 18), fill=FG)
        emit(img, DUR[6] * wfrac)
    card_scene("The reactive transaction, as Lasna's explorer shows it", CAP[5], 7.0,
               "Data read from lasna.reactscan.net (the tx page itself), 2026-11-18.",
               [("Tx Hash", "0x2fab0dfd...78d0859a", FG),
                ("Status", "SUCCESS", GREEN),
                ("Block", "8635792", FG),
                ("From", "0x038E0666...F9bD6B82  (validator)", FG),
                ("Origin event", "verdict tx 0xdafeeea7...  (Base Sepolia)", FG),
                ("Callback #1", "Base vault, dest tx 0xd7d7a15e...", RED)])
    card_scene("The freeze callback, as the explorer shows it", CAP[5], 6.5,
               "Data read from the Ethereum Sepolia explorer, 2026-11-18.",
               [("Tx Hash", "0x98667143...71e577b", FG),
                ("Status", "Success", GREEN),
                ("Block", "12160113", FG),
                ("From", "0xF7E866D7...68A4D91DDb  (relayer)", FG),
                ("To", "0xAa14d9Cd...bd035D23b4  (callback proxy)", FG),
                ("Action", "Deliver Callback — vault frozen", RED)])


def scene7():
    """Animated counter 1..11, then the pace freeze."""
    weights = [(0.45, 10), (0.20, 11), (0.35, 12)]
    for wfrac, upto in weights:
        img, d = base_canvas("Pace freeze — the RSC alone, worker stopped", CAP[6])
        d.text((70, 104), "Worker deliberately shut down for this run.",
               font=font(MONO_B, 20), fill=AMBER)
        d.text((70, 150), "Withdrawal requests across all 3 vaults, this hour:",
               font=font(MONO, 20), fill=FG)
        # counter boxes 1..11
        x, y = 70, 200
        for n in range(1, 12):
            col = RED if (upto >= 11 and n == 11) else (BLUE if n <= upto else DIM)
            d.rectangle([x, y, x + 82, y + 62], outline=col, width=3)
            d.text((x + 26, y + 14), str(n), font=font(MONO_B, 28), fill=col)
            x += 100
            if n == 6:
                x, y = 70, y + 82
        if upto >= 11:
            d.text((70, 380), "11th request  tx 0x6372657f...  [Base]",
                   font=font(MONO, 19), fill=FG)
        if upto >= 12:
            d.text((70, 424), "One Lasna tx: RequestSeen + PaceFreeze + FreezeRequested x3",
                   font=font(MONO_B, 20), fill=RED)
            d.text((70, 462), "tx 0xfd8edbf5... — freeze callbacks land in +2s / +3s / +6s",
                   font=font(MONO, 19), fill=FG)
        emit(img, DUR[7] * wfrac)


def scene8():
    text_scene("Auditable after the fact — real replay output", [
        ("$ python scripts/replay.py --chain 84532 --request-id 3", FG, 19, False),
        ("", FG, 12, False),
        ("  severity:     replay=HIGH  onchain=HIGH  MATCH", GREEN, 20, False),
        ("  score:        replay=713   onchain=713   MATCH", GREEN, 20, False),
        ("  featuresHash: replay == onchain          MATCH", GREEN, 20, False),
        ("  modelHash:    replay == onchain          MATCH", GREEN, 20, False),
        ("  RESULT: MATCH", GREEN, 20, True),
        ("", FG, 12, False),
        ("Also verified from a clean clone, no keys present.", FG, 19, False),
        ("Model ships as JSON in the repo — no pickle.", FG, 19, False),
    ], CAP[7], DUR[8])


def scene9():
    text_scene("Why AI at all? The honest numbers", [
        ("Slow drain to an already-known address", FG, 21, True),
        ("(20 x 0.0079 ETH, 10 min apart, all sub-threshold):", DIM, 19, False),
        ("  fixed rule ...... never flags it", FG, 20, False),
        ("  model v1 / v2 ... never flag it (1h features plateau)", FG, 20, False),
        ("  model v3 ........ flags at step 2 (24h pace features)", GREEN, 20, False),
        ("", FG, 14, False),
        ("Cost of false alarms, held-out normals (n=236):", FG, 20, True),
        ("  model v1: 6 false HIGH (a freeze every ~20 days)", AMBER, 20, False),
        ("  model v3: 0 false HIGH. Full table: eval/RESULTS.md", FG, 20, False),
    ], CAP[8], DUR[9])


def scene10():
    text_scene("Sentinel Vault", [
        ("VerdictRegistry   Base Sepolia  0x0e55C8F8...63abB7F32", FG, 19, False),
        ("SentinelReactive  Lasna         0x48FA2842...4f932A35A7", FG, 19, False),
        ("GuardedVault      Base Sepolia  0xA1eDD9dB...66bBEa703b", FG, 19, False),
        ("GuardedVault      Eth Sepolia   0x3C17336A...9dF734B535", FG, 19, False),
        ("GuardedVault      Unichain Sep. 0x464F45Cf...8002E58bce", FG, 19, False),
        ("", FG, 14, False),
        ("The model's key can post verdicts and nothing else —", BLUE, 20, True),
        ("it cannot move, unfreeze, or reconfigure the vaults.", BLUE, 20, True),
        ("Testnet only — no real funds anywhere in this system.", DIM, 19, False),
    ], CAP[9], DUR[10])


def probe_duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=duration", "-of", "csv=p=0", path],
                       capture_output=True, text=True)
    return float(r.stdout.strip())


def main():
    pad = 1.4
    for i in range(1, 11):
        DUR[i] = probe_duration(os.path.join(NARR, f"scene{i:02d}.mp3")) + pad
    # explorer-card segments extend scenes 4 and 6 beyond narration;
    # those scenes' audio pads with silence (handled in audio build).
    scene_funcs = [scene1, scene2, scene3, scene4, scene5,
                   scene6, scene7, scene8, scene9, scene10]
    scene_starts = []
    for idx, fn in enumerate(scene_funcs, start=1):
        scene_starts.append(len(SEGMENTS))
        fn()
    # crossfades between scenes
    final = []
    for si, start in enumerate(scene_starts):
        end = scene_starts[si + 1] if si + 1 < len(scene_starts) else len(SEGMENTS)
        final.extend(SEGMENTS[start:end])
    list_path = os.path.join(HERE, "frames_v4.txt")
    with open(list_path, "w") as f:
        for path, dur in final:
            f.write(f"file '{path}'\nduration {dur:.3f}\n")
        f.write(f"file '{final[-1][0]}'\n")
    video_only = os.path.join(HERE, "demo_v4_video.mp4")
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_path,
                    "-vf", "fps=30", "-vsync", "cfr", "-pix_fmt", "yuv420p",
                    "-c:v", "libx264", "-movflags", "+faststart", video_only],
                   check=True, capture_output=True)
    # audio: per-scene narration padded to scene length (incl. shot extras)
    scene_lengths = []
    for si, start in enumerate(scene_starts):
        end = scene_starts[si + 1] if si + 1 < len(scene_starts) else len(SEGMENTS)
        scene_lengths.append(sum(d for _, d in SEGMENTS[start:end]))
    ainputs, afilter = [], []
    for i, length in enumerate(scene_lengths, start=1):
        ainputs += ["-i", os.path.join(NARR, f"scene{i:02d}.mp3")]
        afilter.append(f"[{i-1}:a]apad,atrim=0:{length:.3f},aresample=44100[a{i}]")
    afilter.append("".join(f"[a{i}]" for i in range(1, 11)) + "concat=n=10:v=0:a=1[aout]")
    audio_path = os.path.join(HERE, "demo_v4_audio.m4a")
    subprocess.run(["ffmpeg", "-y", *ainputs, "-filter_complex",
                    ";".join(afilter), "-map", "[aout]", "-c:a", "aac", audio_path],
                   check=True, capture_output=True)
    out = os.path.join(HERE, "demo.mp4")
    subprocess.run(["ffmpeg", "-y", "-i", video_only, "-i", audio_path,
                    "-c:v", "copy", "-c:a", "copy", "-shortest", out],
                   check=True, capture_output=True)
    print(f"wrote {out}: {os.path.getsize(out)} bytes, "
          f"duration {probe_duration(out):.1f}s, scenes {scene_lengths}")


if __name__ == "__main__":
    main()
