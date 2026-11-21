#!/usr/bin/env python3
"""Assemble the Sentinel Vault demo video (v3 stack, post-review build).

Every tx hash, score, timestamp delta and log line shown is from the
real 2026-11-18 evidence run recorded in docs/deployments.md.
No mock data. Output: video/demo.mp4 (1280x720, no audio, English
captions burned in). Supersedes make_video.py (v0 stack).
"""
import os
import subprocess

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FRAMES = os.path.join(HERE, "frames_v3")
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

MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
MONO_B = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
SANS_B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
SANS = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


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


def frame(idx, duration, title, body, caption, title_color=FG):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([40, 36, W - 40, H - 130], fill=PANEL)
    d.text((70, 58), title, font=font(SANS_B, 30), fill=title_color)
    y = 112
    for text, color, size, bold in body:
        fnt = font(MONO_B if bold else MONO, size)
        for line in text.split("\n"):
            d.text((70, y), line, font=fnt, fill=color)
            y += int(size * 1.45)
        y += 4
    d.rectangle([0, H - 118, W, H], fill=(0, 0, 0))
    cf = font(SANS, 25)
    lines = wrap(d, caption, cf, W - 120)
    cy = H - 118 + (118 - len(lines) * 34) // 2
    for line in lines:
        d.text((60, cy), line, font=cf, fill=(255, 255, 255))
        cy += 34
    path = os.path.join(FRAMES, f"f{idx:02d}.png")
    img.save(path)
    return path, duration


SCENES = [
    frame(1, 10, "Sentinel Vault", [
        ("When a treasury's hot key is stolen, the first bad", FG, 25, False),
        ("withdrawal on one chain should freeze the others.", FG, 25, False),
        ("", FG, 16, False),
        ("An off-chain model decides.", BLUE, 26, True),
        ("A Reactive contract enforces.", BLUE, 26, True),
        ("The model's key can post verdicts and nothing else.", FG, 24, False),
    ], "Sentinel Vault, for the Reactive Omni Buildathon AI track. An off-chain model decides; a Reactive contract enforces."),
    frame(2, 16, "How it works", [
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
    ], "Large withdrawals queue in a timelock; small ones are capped per hour. The model judges every request, and the Reactive contract also guards the request pace itself."),
    frame(3, 14, "First: the attacks that must fail", [
        ("$ attacker.requestWithdrawal(...)        [not the owner]", FG, 20, False),
        ("  tx 0xf1d85a7b...  status 0  FAILED — reverts NotOwner", RED, 20, True),
        ("", FG, 14, False),
        ("$ owner.unfreeze()                       [daily key, frozen vault]", FG, 20, False),
        ("  tx 0xe04e96ab...  status 0  FAILED — reverts NotRecovery", RED, 20, True),
        ("", FG, 14, False),
        ("Only the offline recovery key can unfreeze or reconfigure.", FG, 20, False),
        ("The daily key cannot lift a freeze placed on itself.", FG, 20, False),
    ], "Requests are owner-only, and the daily key cannot unfreeze: both attacks are real transactions that failed on-chain."),
    frame(4, 20, "Normal withdrawal — judged LOW, executes", [
        ("t+0s    request 0.008 ETH to owner          [Base Sepolia]", FG, 20, False),
        ("        tx 0xeebd5b7e...  (queued, >= threshold)", DIM, 18, False),
        ("t+0s    RSC logs the request (RequestSeen)  [Lasna]", FG, 20, False),
        ("        reactive tx 0x4dfa549d...", DIM, 18, False),
        ("t+10s   [worker] feats=[0.59, 0, 0.69, 0, 0, 0.4, 0, 0]", FG, 20, False),
        ("        -> LOW (583)   verdict tx 0xd9566a09...", GREEN, 20, True),
        ("t+77s   executeWithdrawal() after the wait", FG, 20, False),
        ("        status 1 (success)   tx 0x15edb14c...", GREEN, 20, False),
    ], "A normal withdrawal, with real block timestamps: verdict in ten seconds, executed after the queue wait. Had the AI been silent, it would still execute — fail-open."),
    frame(5, 16, "Burst of withdrawals — MEDIUM vetoes one", [
        ("Three 0.003 ETH requests, seconds apart     [Base Sepolia]", FG, 20, False),
        ("  #1, #2 instant — #3 queued by the hourly instant cap", DIM, 19, False),
        ("", FG, 14, False),
        ("[worker] req 2 -> MEDIUM (662)   tx 0xc928d167...", AMBER, 20, True),
        ("t+1s  RSC VetoRequested                     [Lasna]", FG, 20, False),
        ("      reactive tx 0x3058ab3d...", DIM, 18, False),
        ("t+1s  veto lands via callback proxy", FG, 20, False),
        ("      WithdrawalVetoed   tx 0xa5c2bc1c...", AMBER, 20, False),
    ], "Rapid-fire requests trip the model: a MEDIUM verdict vetoes that one withdrawal, one second from verdict to callback."),
    frame(6, 18, "HIGH — all three vaults freeze pre-emptively", [
        ("[worker] req 3 -> HIGH (713)   tx 0xa0ee51c8...", RED, 20, True),
        ("", FG, 12, False),
        ("RSC FreezeRequested x3                      [Lasna]", FG, 20, False),
        ("  reactive tx 0x2e415642...", DIM, 18, False),
        ("", FG, 12, False),
        ("  freeze callback  Base Sepolia      +2s   frozen = true", RED, 20, False),
        ("  freeze callback  Unichain Sepolia  +2s   frozen = true", RED, 20, False),
        ("  freeze callback  Ethereum Sepolia  +7s   frozen = true", RED, 20, False),
        ("", FG, 12, False),
        ("A later request while frozen: tx 0x072d0415... FAILED (VaultFrozen)", FG, 18, False),
    ], "One HIGH verdict freezes the vaults on all three chains within seconds — before the queued withdrawal can execute. Recovery-key unfreeze only."),
    frame(7, 16, "Pace freeze — the RSC alone, worker stopped", [
        ("Worker deliberately shut down for this run.", AMBER, 20, True),
        ("", FG, 14, False),
        ("11th withdrawal request within one hour, across chains:", FG, 20, False),
        ("  tx 0x0af58b70...                          [Base Sepolia]", DIM, 19, False),
        ("", FG, 14, False),
        ("One Lasna reactive tx: RequestSeen + PaceFreeze", FG, 20, False),
        ("  + FreezeRequested x3    tx 0xf5aeb1e9...", DIM, 19, False),
        ("  freeze callbacks land in +2s / +3s / +6s", RED, 20, False),
        ("", FG, 14, False),
        ("No AI verdict involved. The contract guards pace itself.", FG, 20, False),
    ], "Even with the AI worker down, the Reactive contract freezes everything when the cross-chain request pace crosses ten per hour."),
    frame(8, 16, "Auditable after the fact — real replay output", [
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
    ], "Every verdict carries feature and model hashes. This is the actual replay output: anyone can recompute a verdict from chain data and check it."),
    frame(9, 16, "Why AI at all? The honest numbers", [
        ("Slow drain to an already-known address", FG, 21, True),
        ("(20 x 0.0079 ETH, 10 min apart, all sub-threshold):", DIM, 19, False),
        ("  fixed rule ...... never flags it", FG, 20, False),
        ("  model v1 / v2 ... never flag it (1h features plateau)", FG, 20, False),
        ("  model v3 ........ flags at step 2 (24h pace features)", GREEN, 20, False),
        ("", FG, 14, False),
        ("Cost of false alarms, held-out normals (n=236):", FG, 20, True),
        ("  model v1: 6 false HIGH (a freeze every ~20 days)", AMBER, 20, False),
        ("  model v3: 0 false HIGH. Full table: eval/RESULTS.md", FG, 20, False),
    ], "A fixed rule cannot see a slow drain; the model can, after we closed its blind spot. We publish the false-alarm costs too — the claim is bounded damage, not trustless."),
    frame(10, 10, "Sentinel Vault", [
        ("VerdictRegistry   Base Sepolia  0x0e55C8F8...63abB7F32", FG, 19, False),
        ("SentinelReactive  Lasna         0xeaE20ecc...8CC21a1ff8", FG, 19, False),
        ("GuardedVault      Base Sepolia  0xAf17d1e2...F95Aef3DE4", FG, 19, False),
        ("GuardedVault      Eth Sepolia   0x0C0c5477...B02335d395BED", FG, 19, False),
        ("GuardedVault      Unichain Sep. 0x95Fd0764...aa1410b19b2d", FG, 19, False),
        ("", FG, 14, False),
        ("The model's key can post verdicts and nothing else —", BLUE, 20, True),
        ("it cannot move, unfreeze, or reconfigure the vaults.", BLUE, 20, True),
        ("Testnet only — no real funds anywhere in this system.", DIM, 19, False),
    ], "Sentinel Vault: the model decides, the Reactive contract enforces, and neither can move the funds. Thank you for watching."),
]


def main():
    list_path = os.path.join(HERE, "frames_v3.txt")
    with open(list_path, "w") as f:
        for path, dur in SCENES:
            f.write(f"file '{path}'\nduration {dur}\n")
        f.write(f"file '{SCENES[-1][0]}'\n")
    out = os.path.join(HERE, "demo.mp4")
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_path,
        "-vsync", "vfr", "-pix_fmt", "yuv420p", "-c:v", "libx264",
        "-movflags", "+faststart", out,
    ], check=True, capture_output=True)
    total = sum(d for _, d in SCENES)
    print(f"wrote {out}: {os.path.getsize(out)} bytes, ~{total}s")


if __name__ == "__main__":
    main()
