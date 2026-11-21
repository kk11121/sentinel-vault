Demo video: video/demo.mp4 — the shipped submission video (140 s,
1280x720), built by video/make_video_v7.py from the v5/v6 stack
evidence run of 2026-11-18: English TTS narration with burned-in
captions, tightened pacing, a quiet procedural BGM track and soft
accent sounds at the veto / freeze / replay moments. Narration text:
video/narration_v6.py (reused by v7). Regenerate:
.venv/bin/python video/make_video_v7.py

video/make_video_v6.py is the previous builder (same narration,
longer pacing, no BGM) and is kept as the fallback. The superseded
builders (make_video.py, make_video_v3.py, make_video_v4.py) and
their frame sets live in archive/video/ for provenance; the demo_*
audio/video intermediates are build artifacts of the v4/v6/v7
renders.
