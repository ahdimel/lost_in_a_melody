"""Stage 5a — TEMPO: seconds → tempo-relative beats (D8).

Phase 0 clarified that absolute BPM and meter don't matter for playing — only the
sequence and *relative* durations do, and those survive a wrong tempo. So:
  - `detect_bpm` gives a rough default (librosa),
  - the owner can override it (a wrong guess must never block anything),
  - quantization is **gentle and optional** — over-aggressive snapping is the only
    thing that can actually corrupt relative durations.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from .notes import Note

# (start_beat, length_beat, midi_pitch)
BeatNote = tuple[float, float, int]

DEFAULT_GRID = 0.25   # gentle: snap to 1/4-beat (16th notes); None disables


def detect_bpm(clip: Path) -> float:
    """Rough BPM estimate for a default. Owner-overridable; never authoritative."""
    import librosa  # lazy: heavy import

    y, sr = librosa.load(str(clip), sr=None, mono=True)
    tempo, _beats = librosa.beat.beat_track(y=y, sr=sr, units="time")
    bpm = float(np.atleast_1d(tempo)[0])
    return round(bpm, 1) if bpm > 0 else 120.0


def _snap(value: float, grid: float | None) -> float:
    if not grid:
        return round(value, 4)
    return round(round(value / grid) * grid, 4)


def to_beats(notes: list[Note], bpm: float,
             *, quantize: float | None = DEFAULT_GRID) -> list[BeatNote]:
    """Convert second-timed notes to (start_beat, length_beat, pitch).

    A quantized length is floored to one grid unit so no note vanishes.
    """
    spb = 60.0 / bpm
    out: list[BeatNote] = []
    for n in notes:
        start_b = _snap(n.start / spb, quantize)
        length_b = _snap(n.duration / spb, quantize)
        if quantize:
            length_b = max(quantize, length_b)
        elif length_b <= 0:
            length_b = round(n.duration / spb, 4)
        out.append((start_b, length_b, n.pitch))
    return out
