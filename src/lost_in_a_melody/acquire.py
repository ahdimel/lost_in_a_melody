"""Stage 1 — ACQUIRE: URL or local file → normalized, trimmed `clip.wav`.

Fetches with yt-dlp (invoked as `python -m yt_dlp` so it works without the console
script on PATH), then trims + normalizes with ffmpeg to mono 44.1 kHz — the format
the separation and transcription models expect.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

SAMPLE_RATE = 44100


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def _ffmpeg_trim(src: Path, dest: Path, start: float | None, end: float | None) -> None:
    cmd = ["ffmpeg", "-y"]
    if start is not None:
        cmd += ["-ss", str(start)]
    if end is not None:
        cmd += ["-t", str((end - (start or 0.0)))]
    cmd += ["-i", str(src), "-ac", "1", "-ar", str(SAMPLE_RATE), str(dest)]
    _run(cmd)


def fetch_url(url: str, dest_raw: Path) -> Path:
    """Download best audio for `url` to a WAV at `dest_raw` (no trim)."""
    dest_raw.parent.mkdir(parents=True, exist_ok=True)
    template = str(dest_raw.with_suffix("")) + ".%(ext)s"
    _run([sys.executable, "-m", "yt_dlp", "-x", "--audio-format", "wav",
          "-o", template, url])
    return dest_raw


def acquire(source: str, out_wav: Path, *, is_url: bool,
            start: float | None = None, end: float | None = None) -> Path:
    """Produce a trimmed, normalized `clip.wav` at `out_wav`.

    `source` is a URL (is_url=True) or a local audio path. `start`/`end` are seconds.
    """
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        if is_url:
            raw = fetch_url(source, Path(td) / "raw.wav")
        else:
            raw = Path(source).expanduser()
            if not raw.exists():
                raise FileNotFoundError(f"local audio not found: {raw}")
        _ffmpeg_trim(raw, out_wav, start, end)
    return out_wav


def ingest_full(source: str, out_wav: Path, *, is_url: bool) -> Path:
    """Fetch/normalize the WHOLE source (untrimmed) to `out_wav`.

    The GUI stores this so the browser can play the full source and the owner can
    drag a trim range over it before committing to a clip. `acquire()` (used by the
    CLI) fetches + trims in one shot; this splits the fetch off from the trim.
    """
    return acquire(source, out_wav, is_url=is_url, start=None, end=None)


def trim(src_wav: Path, out_wav: Path, start: float | None, end: float | None) -> Path:
    """Trim an already-normalized WAV to [start, end] seconds → `out_wav`."""
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    _ffmpeg_trim(src_wav, out_wav, start, end)
    return out_wav
