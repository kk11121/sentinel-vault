#!/usr/bin/env python3
"""Sentinel Vault demo video v6 — narrated, animated, with
explorer-style cards.

All data (tx hashes, scores, timings) is from the real 2026-11-18
v5/v6 evidence run in docs/deployments.md. The explorer cards are
rendered from data read live from the chains/explorers on
2026-11-18 (Basescan's own pages were behind a Cloudflare bot wall
for our browser, so its data was taken from the mirror explorer /
RPC reads instead).
Narration: video/narration_v6/sceneNN.mp3 (TTS, see narration_v6.py).
Output: video/demo.mp4 (1280x720, English narration + burned-in
captions). Supersedes make_video_v4.py.
"""
import math
import os
import struct
import subprocess
import wave

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FRAMES = os.path.join(HERE, "frames_v7")
SHOTS = os.path.join(HERE, "shots")
NARR = os.path.join(HERE, "narration_v6")
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
    "First, the attacks that must fail: a non-owner's request reverts, the daily key cannot unfreeze its own vault, a stranger cannot cancel a queue — and a verdict about an unwatched vault is ignored.",
    "A normal withdrawal: the Reactive contract logs the request, the model scores it LOW in eleven seconds, and it executes after the wait. Fail-open by design.",
    "On Ethereum Sepolia, a MEDIUM verdict vetoes exactly one withdrawal — nothing else freezes. A second MEDIUM within the hour escalates to a freeze of all three vaults.",
    "One HIGH verdict vetoes its own request and freezes the vaults on all three chains — and the flagged request stays dead even after an unfreeze.",
    "With the worker deliberately stopped, the eleventh request in an hour makes the Reactive contract freeze everything by itself.",
    "Every verdict carries feature and model hashes. The replay recomputes them from chain data — all four fields MATCH.",
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
        ("$ attacker.requestWithdrawal(...)     [not the owner]", FG, 20, False),
        ("  eth_call — reverts NotOwner", RED, 20, True),
        ("$ owner.unfreeze()                    [daily key]", FG, 20, False),
        ("  eth_call — reverts NotRecovery", RED, 20, True),
        ("$ stranger.cancelWithdrawal(6)        [not the requester]", FG, 20, False),
        ("  eth_call — reverts NotRequester", RED, 20, True),
        ("", FG, 14, False),
        ("HIGH verdict (999) naming an UNWATCHED vault  [posted on-chain]", FG, 20, False),
        ("  tx 0xc3515b45...  ->  RSC: VerdictForUnwatched — ignored", AMBER, 20, True),
        ("  reactive tx 0x9a57eec6...  [Lasna] — no veto, no freeze", FG, 20, False),
    ], CAP[2], DUR[3])


def scene4():
    """Animated timeline: request -> verdict (+7s) -> executed (+98s)."""
    steps = [
        (0.30, 1), (0.25, 2), (0.25, 3), (0.20, 4),
    ]
    events = [
        ("t+0s   request 0.001 ETH to owner  [Base]", "tx 0xa2cd8b68...", FG),
        ("t+0s   RSC logs RequestSeen  [Lasna reactive tx]", "tx 0x589c68f6...", FG),
        ("t+11s  verdict LOW (522)  [Base]", "tx 0x6f3da7d6...", GREEN),
        ("       executed after the wait  [Base]", "tx 0xbaa2fa62...", GREEN),
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
    card_scene("The verdict, as the explorer shows it", CAP[3], 4.2,
               "Data read from the Base Sepolia explorer (Blockscout API), 2026-11-18.",
               [("Tx Hash", "0x6f3da7d6...c3480a59", FG),
                ("Status", "Success", GREEN),
                ("Block", "60441957", FG),
                ("From", "0xD4bdEb62...F9B9c307  (verdictWriter)", FG),
                ("To", "0x0e55C8F8...63abB7F32  (VerdictRegistry)", FG),
                ("Action", "postVerdict — LOW, score 522", GREEN)])


def scene5():
    text_scene("MEDIUM — veto one request only; twice escalates", [
        ("Withdrawals to the owner address       [Ethereum Sepolia]", FG, 20, False),
        ("", FG, 14, False),
        ("[worker] req 2 -> MEDIUM (624)   tx 0x98ef6e72...", AMBER, 20, True),
        ("  RSC vetoes ONLY req 2 via the callback proxy", FG, 20, False),
        ("      WithdrawalVetoed   tx 0x9c2206e5...", AMBER, 20, False),
        ("  all three vaults read back UNFROZEN afterwards", FG, 20, False),
        ("", FG, 14, False),
        ("[worker] req 3 -> MEDIUM (627) — 2nd within the hour", AMBER, 20, True),
        ("  RSC escalates: veto + freeze ALL   tx 0xb931eedf...  [Lasna]", RED, 20, False),
    ], CAP[4], DUR[5])


def scene6():
    """Animated freeze propagation across the three vault boxes."""
    chains = [
        ("GuardedVault — Base Sepolia", "callback tx 0xf8393de4..."),
        ("GuardedVault — Unichain Sepolia", "callback tx 0x70f34099..."),
        ("GuardedVault — Ethereum Sepolia", "callback tx 0xfa750ebb..."),
    ]
    phases = [0, 1, 2, 3]  # how many boxes are frozen
    weights = [0.34, 0.22, 0.22, 0.22]
    for frozen_count, wfrac in zip(phases, weights):
        img, d = base_canvas("HIGH — all three vaults freeze pre-emptively", CAP[5])
        d.text((70, 104), "[worker] Base req 2 -> HIGH (735)   tx 0x5d192de1...",
               font=font(MONO_B, 20), fill=RED)
        d.text((70, 140), "RSC VetoRequested + FreezeRequested x3   reactive tx 0xfe429e3c...  [Lasna]",
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
            d.text((70, y + 6), "Veto of the flagged request: tx 0x9c981fc1... — after an unfreeze, executing it",
                   font=font(MONO, 18), fill=FG)
            d.text((70, y + 32), "still FAILS (tx 0x66bc581d..., reverts Vetoed)",
                   font=font(MONO, 18), fill=FG)
        emit(img, DUR[6] * wfrac)
    card_scene("The reactive transaction, as Lasna's explorer shows it", CAP[5], 4.8,
               "Data read from lasna.reactscan.net (the tx page itself), 2026-11-18.",
               [("Tx Hash", "0xfe429e3c...b720a2", FG),
                ("Status", "SUCCESS", GREEN),
                ("Block", "8657074", FG),
                ("From", "0x038E0666...F9bD6B82  (validator)", FG),
                ("Origin event", "verdict tx 0x5d192de1...  (Base Sepolia)", FG),
                ("Callback #1", "Base vault, dest tx 0x9c981fc1...", RED)])
    card_scene("The freeze callback, as the explorer shows it", CAP[5], 4.2,
               "Data read from the Base Sepolia explorer (Blockscout API), 2026-11-18.",
               [("Tx Hash", "0xf8393de4...365ee03", FG),
                ("Status", "Success", GREEN),
                ("Block", "60442868", FG),
                ("From", "0xF7E866D7...68A4D91DDb  (relayer)", FG),
                ("To", "0x476F44b1...710743585  (callback proxy)", FG),
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
            d.text((70, 380), "11th request  tx 0x6196bba9...  [Base]",
                   font=font(MONO, 19), fill=FG)
        if upto >= 12:
            d.text((70, 424), "One Lasna tx: RequestSeen + PaceFreeze + FreezeRequested x3",
                   font=font(MONO_B, 20), fill=RED)
            d.text((70, 462), "tx 0x81c35c28... — Base freeze callback tx 0xf3349ce5...",
                   font=font(MONO, 19), fill=FG)
        emit(img, DUR[7] * wfrac)


def scene8():
    text_scene("Auditable after the fact — real replay output", [
        ("$ python scripts/replay.py --chain 84532 --request-id 2", FG, 19, False),
        ("", FG, 12, False),
        ("  severity:     replay=HIGH  onchain=HIGH  MATCH", GREEN, 20, False),
        ("  score:        replay=735   onchain=735   MATCH", GREEN, 20, False),
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
        ("SentinelReactive  Lasna         0x00eC75c1...8cF3Eb06", FG, 19, False),
        ("GuardedVault      Base Sepolia  0x1Eb81CC9...27369c6f4", FG, 19, False),
        ("GuardedVault      Eth Sepolia   0xd8D640De...82BA118Ad6", FG, 19, False),
        ("GuardedVault      Unichain Sep. 0xAf17d1e2...F95Aef3DE4", FG, 19, False),
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


SR = 44100


def _write_wav(path, samples):
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(b"".join(
            struct.pack("<h", int(max(-1.0, min(1.0, s)) * 32767))
            for s in samples))


def write_bgm(path, total):
    """Quiet procedural pad: Am - F - C - G sine chords, crossfaded."""
    chords = [(110.00, 164.81, 261.63), (87.31, 174.61, 261.63),
              (130.81, 196.00, 329.63), (98.00, 196.00, 293.66)]
    amps = (0.055, 0.038, 0.030)
    seg = total / len(chords)
    fade = 1.5
    out = [0.0] * int(total * SR)

    def add_chord(ch, start_s, dur_s, fade_in, fade_out):
        i0 = int(start_s * SR)
        i1 = min(len(out), int((start_s + dur_s) * SR))
        for i in range(i0, i1):
            t = i / SR
            lt = t - start_s
            g = 1.0
            if fade_in and lt < fade_in:
                g = min(g, lt / fade_in)
            rem = dur_s - lt
            if fade_out and rem < fade_out:
                g = min(g, rem / fade_out)
            out[i] += g * sum(a * math.sin(2 * math.pi * f * t)
                              for f, a in zip(ch, amps))

    for ci, ch in enumerate(chords):
        start = ci * seg - (fade if ci else 0.0)
        dur = seg + (fade if ci else 0.0) + (fade if ci < len(chords) - 1 else 0.0)
        add_chord(ch, max(0.0, start), dur, fade if ci else 2.0,
                  fade if ci < len(chords) - 1 else 3.0)
    _write_wav(path, out)


def _sweep(f0, f1, dur, tau, peak):
    n = int(dur * SR)
    return [peak * math.sin(2 * math.pi * (f0 * (i / SR)
            + (f1 - f0) * (i / SR) ** 2 / (2 * dur)))
            * math.exp(-(i / SR) / tau) for i in range(n)]


def write_blip(path):
    _write_wav(path, _sweep(620, 415, 0.20, 0.05, 0.5))


def write_thud(path):
    _write_wav(path, _sweep(130, 58, 0.24, 0.07, 0.6))


def write_ding(path):
    n = int(0.60 * SR)
    out = [0.0] * n
    for i in range(n):
        t = i / SR
        v = 0.30 * math.sin(2 * math.pi * 880 * t) * math.exp(-t / 0.13)
        if t > 0.07:
            v += 0.18 * math.sin(2 * math.pi * 1174.66 * (t - 0.07)) \
                * math.exp(-(t - 0.07) / 0.10)
        out[i] = v
    _write_wav(path, out)


def main():
    pad = 0.9
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
    list_path = os.path.join(HERE, "frames_v6.txt")
    with open(list_path, "w") as f:
        for path, dur in final:
            f.write(f"file '{path}'\nduration {dur:.3f}\n")
        f.write(f"file '{final[-1][0]}'\n")
    video_only = os.path.join(HERE, "demo_v7_video.mp4")
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
    narr_path = os.path.join(HERE, "narration_v7.m4a")
    subprocess.run(["ffmpeg", "-y", *ainputs, "-filter_complex",
                    ";".join(afilter), "-map", "[aout]", "-c:a", "aac", narr_path],
                   check=True, capture_output=True)
    # light polish: quiet procedural BGM ducked under the narration,
    # plus soft synthesized accents at the veto / freeze / match moments.
    total = sum(scene_lengths)
    starts = [sum(scene_lengths[:k]) for k in range(10)]
    bgm_path = os.path.join(HERE, "bgm_v7.wav")
    write_bgm(bgm_path, total)
    blip = os.path.join(HERE, "sfx_blip.wav")
    thud = os.path.join(HERE, "sfx_thud.wav")
    ding = os.path.join(HERE, "sfx_ding.wav")
    write_blip(blip)
    write_thud(thud)
    write_ding(ding)
    sfx = [(blip, starts[4] + 1.2, 0.50)]
    for frac in (0.34, 0.56, 0.78):
        sfx.append((thud, starts[5] + frac * DUR[6], 0.55))
    sfx.append((blip, starts[6] + 0.45 * DUR[7], 0.35))
    sfx.append((thud, starts[6] + 0.65 * DUR[7], 0.65))
    sfx.append((ding, starts[7] + 0.8, 0.50))
    minputs = ["-i", narr_path, "-i", bgm_path]
    for path, _, _ in sfx:
        minputs += ["-i", path]
    mg = ["[1:a]volume=0.55[bgm0]",
          "[bgm0][0:a]sidechaincompress=threshold=0.03:ratio=6:attack=40:release=350[bgmd]"]
    labels = ["[0:a]", "[bgmd]"]
    for j, (_, delay, gain) in enumerate(sfx):
        ms = int(delay * 1000)
        mg.append(f"[{j+2}:a]adelay={ms}|{ms},volume={gain}[s{j}]")
        labels.append(f"[s{j}]")
    mg.append("".join(labels)
              + f"amix=inputs={len(labels)}:duration=first:dropout_transition=0:normalize=0,alimiter=limit=0.95[aout]")
    mixed = os.path.join(HERE, "demo_v7_audio.m4a")
    subprocess.run(["ffmpeg", "-y", *minputs, "-filter_complex", ";".join(mg),
                    "-map", "[aout]", "-c:a", "aac", mixed],
                   check=True, capture_output=True)
    out = os.path.join(HERE, "demo.mp4")
    subprocess.run(["ffmpeg", "-y", "-i", video_only, "-i", mixed,
                    "-c:v", "copy", "-c:a", "copy", "-shortest", out],
                   check=True, capture_output=True)
    print(f"wrote {out}: {os.path.getsize(out)} bytes, "
          f"duration {probe_duration(out):.1f}s, scenes {scene_lengths}")


if __name__ == "__main__":
    main()
