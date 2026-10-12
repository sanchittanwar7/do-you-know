"""ffmpeg: stitch carousel slides into a 9:16 reel video with optional audio.

Each slide gets a draining progress bar ("sliding timer") below its header.
Slides run for different durations set via REEL_QUESTION/SHORT/LONG_SECONDS.

The Instagram Graph API cannot attach licensed/trending music to a reel; the
only way to get audio onto a reel through the API is to bake it into the video
file. `REEL_MUSIC_PATH` (or an explicit `music_path` argument) points at an
audio file you own or are licensed to use.
"""
import os
import random
import shutil
import subprocess

from .config import (
    BG,
    FG,
    IMG_H,
    OUT_DIR,
    REEL_AUDIO_DIR,
    REEL_CROSSFADE,
    REEL_FPS,
    REEL_H,
    REEL_LONG_SECONDS,
    REEL_MUSIC_PATH,
    REEL_MUSIC_VOLUME,
    REEL_QUESTION_SECONDS,
    REEL_SHORT_SECONDS,
    REEL_TIMER_HEIGHT,
    REEL_TIMER_WIDTH_FRACTION,
    REEL_TIMER_Y,
    REEL_W,
)

_AUDIO_EXTS = {".mp3", ".m4a", ".wav", ".aac", ".ogg", ".flac"}


def _ffmpeg():
    path = shutil.which("ffmpeg")
    if not path:
        raise RuntimeError("ffmpeg not found on PATH. Install it (e.g. apt install ffmpeg).")
    return path


def _hex(color):
    r, g, b = color
    return f"0x{r:02x}{g:02x}{b:02x}"


def _timer_geometry():
    """Width, x, and y of the centered timer bar on the video canvas."""
    track_w = int(REEL_W * REEL_TIMER_WIDTH_FRACTION)
    track_x = (REEL_W - track_w) // 2
    timer_y = (REEL_H - IMG_H) // 2 + REEL_TIMER_Y
    return track_w, track_x, timer_y


def _pick_music(explicit=None):
    """Resolve a background track: explicit arg > REEL_MUSIC_PATH > random dir."""
    if explicit:
        if os.path.exists(explicit):
            return explicit
        raise RuntimeError(f"Reel music file not found: {explicit}")
    if REEL_MUSIC_PATH:
        if os.path.exists(REEL_MUSIC_PATH):
            return REEL_MUSIC_PATH
        raise RuntimeError(f"Reel music file not found: {REEL_MUSIC_PATH}")
    if REEL_AUDIO_DIR.is_dir():
        tracks = [p for p in REEL_AUDIO_DIR.iterdir() if p.suffix.lower() in _AUDIO_EXTS]
        if tracks:
            return str(random.choice(tracks))
    return None


def _slide_durations(n):
    """Per-slide durations in order: question, short, long, then long again."""
    base = [REEL_QUESTION_SECONDS, REEL_SHORT_SECONDS, REEL_LONG_SECONDS]
    out = list(base[:n])
    while len(out) < n:
        out.append(REEL_LONG_SECONDS)
    return out[:n]


def build_reel(slide_paths, draft_id, music_path=None):
    """Stitch slides into out/<draft_id>/reel.mp4 and return a repo-relative path.

    Slides are letterboxed onto a 9:16 canvas (cream bars, no cropping), each
    gets a draining timer bar, and they are joined with a fade crossfade. If
    music is configured, it is mixed in and faded out over the last 1.5s.
    """
    ffmpeg = _ffmpeg()
    out_dir = OUT_DIR / draft_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "reel.mp4"

    n = len(slide_paths)
    durations = _slide_durations(n)
    fade = REEL_CROSSFADE
    total = sum(durations) - (n - 1) * fade

    cmd = [ffmpeg, "-y"]
    for i, p in enumerate(slide_paths):
        resolved = str(p) if os.path.isabs(p) else str(OUT_DIR.parent / p)
        cmd += ["-loop", "1", "-t", f"{durations[i]}", "-i", resolved]

    music = _pick_music(music_path)
    audio_index = None
    if music:
        audio_index = n
        cmd += ["-i", music]

    scale_filter = (
        f"scale={REEL_W}:{REEL_H}:force_original_aspect_ratio=decrease,"
        f"pad={REEL_W}:{REEL_H}:(ow-iw)/2:(oh-ih)/2:color={_hex(BG)},"
        f"setsar=1,fps={REEL_FPS}"
    )

    track_w, track_x, timer_y = _timer_geometry()

    parts = []
    for i, dur in enumerate(durations):
        parts.append(f"[{i}:v]{scale_filter}[base{i}]")
        parts.append(
            f"color=c=0x000000@0.0:s={track_w}x{REEL_TIMER_HEIGHT}:"
            f"r={REEL_FPS}:d={dur},format=rgba[clip{i}]"
        )
        parts.append(
            f"color=c={_hex(FG)}:s={track_w}x{REEL_TIMER_HEIGHT}:"
            f"r={REEL_FPS}:d={dur},format=rgba[fill{i}]"
        )
        # Drain the fill leftward within a transparent clip so it shrinks from
        # the right and never spills past its left anchor. No track is drawn.
        parts.append(f"[clip{i}][fill{i}]overlay=x='-w*t/{dur}':y=0[tf{i}]")
        parts.append(f"[base{i}][tf{i}]overlay={track_x}:{timer_y}[seg{i}]")

    prev = "seg0"
    for i in range(1, n):
        offset = sum(durations[:i]) - i * fade
        out = f"x{i}" if i < n - 1 else "vout"
        parts.append(
            f"[{prev}][seg{i}]xfade=transition=fade:duration={fade}:offset={offset:.3f}[{out}]"
        )
        prev = out
    if n == 1:
        parts.append("[seg0]null[vout]")

    cmd += [
        "-filter_complex",
        ";".join(parts),
        "-map",
        "[vout]",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-r",
        str(REEL_FPS),
    ]

    if audio_index is not None:
        cmd += [
            "-map",
            f"{audio_index}:a:0",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-af",
            f"volume={REEL_MUSIC_VOLUME},afade=t=out:st={max(total - 1.5, 0):.3f}:d=1.5",
            "-shortest",
        ]
    else:
        cmd += ["-an"]

    cmd.append(str(out_path))

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr[-2000:]}")
    return f"out/{draft_id}/reel.mp4"
