#!/usr/bin/env python3
"""Assemble the Sentinel Vault demo video from captioned frames.

Every tx hash, score and log line shown is from the real filmed run
recorded in docs/deployments.md (2026-11-17). No mock data.
Output: video/demo.mp4 (1280x720, no audio, English captions burned in).
"""
import os
import subprocess
import textwrap

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FRAMES = os.path.join(HERE, "frames")
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
CAPTION_BG = (0, 0, 0)

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
    """body: list of (text, color, size, bold) tuples, drawn as lines."""
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
    # caption bar
    d.rectangle([0, H - 118, W, H], fill=CAPTION_BG)
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
    frame(1, 12, "Sentinel Vault", [
        ("An AI-guarded vault for the Reactive Omni Buildathon", BLUE, 24, True),
        ("", FG, 18, False),
        ("The AI judges every withdrawal.", FG, 26, False),
        ("A Reactive contract does the stopping.", FG, 26, False),
        ("The AI's key can never move funds.", FG, 26, False),
    ], "Sentinel Vault: an AI judges every withdrawal. A Reactive contract does the stopping. The AI's key can never move funds."),
    frame(2, 17, "How it works", [
        ("GuardedVault x3 chains        VerdictRegistry        SentinelReactive", FG, 19, True),
        ("(Base / Eth Sepolia /         (Base Sepolia)         (Lasna, RSC)", DIM, 19, False),
        (" Unichain Sepolia)", DIM, 19, False),
        ("", FG, 14, False),
        ("  withdrawal request ──► worker: 6 features", FG, 20, False),
        ("                         Isolation Forest scores it", FG, 20, False),
        ("                         verdict posted on-chain ──► RSC reacts:", FG, 20, False),
        ("", FG, 14, False),
        ("  LOW ..... nothing (withdrawal executes, fail-open)", GREEN, 20, False),
        ("  MEDIUM .. veto that one withdrawal", AMBER, 20, False),
        ("  HIGH .... freeze ALL three vaults, pre-emptively", RED, 20, False),
        ("  2x MEDIUM within 1h escalates to HIGH", RED, 20, False),
    ], "Large withdrawals wait in a timelock queue. The model scores every request; the Reactive contract vetoes or freezes. Silence from the AI never blocks funds."),
    frame(3, 19, "Normal withdrawal — judged LOW", [
        ("$ vault.requestWithdrawal(to=owner, 0.008 ETH)   [Base Sepolia]", FG, 19, False),
        ("  tx 0xa71fab2b85115a32e79e028a901b3012f754e123fb62b631bd37f9774cf3d088", DIM, 16, False),
        ("", FG, 14, False),
        ("[worker] req 6  feats=[0.59, 0.0, 0.69, 0.0, 0.0, 0.4]", FG, 19, False),
        ("         -> LOW (562)   verdict tx 0xbc136b15...", GREEN, 19, True),
        ("", FG, 14, False),
        ("$ vault.executeWithdrawal(6)        # after the 60 s wait", FG, 19, False),
        ("  status 1 (success)   tx 0x627e22b570ae0df4c4f0ba4cf0cdd...", GREEN, 19, False),
        ("  0.008 ETH delivered to the owner", FG, 19, False),
    ], "A normal withdrawal to a known address: judged LOW, executed after the waiting period. If the AI were offline, it would still execute — fail-open by design."),
    frame(4, 19, "Attack — first-seen destination", [
        ("$ vault.requestWithdrawal(to=0x63B6...5672, 0.008 ETH)", FG, 19, False),
        ("  tx 0x86cc98e93af0e2a642c5a888033147a9cdaf59538a1322b83f3debaeb605d72f", DIM, 16, False),
        ("", FG, 14, False),
        ("[worker] req 7  feats=[0.59, 1.0, 0.0, 0.1, 0.59, 0.67]", FG, 19, False),
        ("         first_seen=1.0, balance_ratio=0.67", AMBER, 19, False),
        ("         -> HIGH (728)   verdict tx 0x760a6056...", RED, 19, True),
    ], "A withdrawal to a never-seen address, two thirds of the vault balance: the model flags it HIGH and posts the verdict on-chain."),
    frame(5, 17, "The Reactive contract freezes everything", [
        ("SentinelReactive.react()  ->  freeze callbacks to 3 chains", FG, 20, False),
        ("", FG, 14, False),
        ("  GuardedVault (Base Sepolia)       frozen() = true", RED, 21, False),
        ("  GuardedVault (Ethereum Sepolia)   frozen() = true", RED, 21, False),
        ("  GuardedVault (Unichain Sepolia)   frozen() = true", RED, 21, False),
        ("", FG, 14, False),
        ("$ vault.executeWithdrawal(7)", FG, 19, False),
        ("  Error: execution reverted: VaultFrozen", RED, 19, True),
    ], "The HIGH verdict freezes all three vaults pre-emptively — before any money moves. No server sits in the enforcement path; the Reactive contract executes it."),
    frame(6, 18, "Auditable after the fact", [
        ("$ python scripts/replay.py --chain 84532 --request-id 7", FG, 19, False),
        ("", FG, 14, False),
        ("  severity:     replay=HIGH   onchain=HIGH   MATCH", GREEN, 20, False),
        ("  score:        replay=728    onchain=728    MATCH", GREEN, 20, False),
        ("  featuresHash: 0x16cf2577...  == on-chain   MATCH", GREEN, 20, False),
        ("  modelHash:    0xc65a9db6...  == on-chain   MATCH", GREEN, 20, False),
        ("", FG, 14, False),
        ("Model ships as JSON in the repo (no pickle).", FG, 19, False),
        ("modelHash = keccak256 of the exact model file.", FG, 19, False),
    ], "Every verdict carries the feature hash and the model hash. Anyone can recompute it from chain data and check — this replay matches on all four fields."),
    frame(7, 18, "Honest evaluation (synthetic data)", [
        ("Held-out normal traffic flagged >= MEDIUM:", FG, 20, True),
        ("  fixed rule  0.8%        model  3.8%   <- model is noisier", AMBER, 20, False),
        ("", FG, 14, False),
        ("Full drain:        both flag HIGH on withdrawal #1", FG, 20, False),
        ("Small-amount barrage: only the model reaches HIGH", FG, 20, False),
        ("Rare legit, 3x median to a known address:", FG, 20, False),
        ("  rule passes (LOW)     model flags HIGH  <- false alarm", AMBER, 20, False),
        ("", FG, 14, False),
        ("Full table: eval/RESULTS.md — published as computed.", DIM, 19, False),
    ], "We publish the evaluation as computed, including where the model loses. The claim is bounded damage and auditability — not 'trustless'."),
    frame(8, 13, "Sentinel Vault", [
        ("VerdictRegistry   Base Sepolia  0xEe60c977...B28A12", FG, 19, False),
        ("SentinelReactive  Lasna         0x946181Fe...524262e", FG, 19, False),
        ("GuardedVault      Base Sepolia  0xFf25f82b...02D2b926", FG, 19, False),
        ("GuardedVault      Eth Sepolia   0x95Fd0764...a1410b19b2d", FG, 19, False),
        ("GuardedVault      Unichain Sep. 0x68A10a67...2380Dc5560", FG, 19, False),
        ("", FG, 14, False),
        ("All links, code and tx evidence: see the repository.", BLUE, 20, True),
        ("Testnet only — no real funds anywhere in this system.", DIM, 19, False),
    ], "Sentinel Vault: the detection AI's key never touches funds, and the stopping is done by a Reactive contract. Thank you for watching."),
]


def main():
    list_path = os.path.join(HERE, "frames.txt")
    with open(list_path, "w") as f:
        for path, dur in SCENES:
            f.write(f"file '{path}'\nduration {dur}\n")
        f.write(f"file '{SCENES[-1][0]}'\n")  # concat demuxer needs last frame repeated
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
