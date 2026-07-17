"""Stage 3 — PICK STEM: rank stems by signal energy, suggest the tune-carrier.

Phase 0 lesson: score by **RMS energy**, not note count. An empty stem transcribes
to a few sparse artifacts that *look* like a clean melody but are silence. Energy
correctly put piano ~4× above the rest on a piano song, and vocals above guitar on a
vocal song. Drums/bass are excluded as candidates — they don't carry tunes.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf

# stems that can plausibly carry a melody (exclude percussion / bass line)
CANDIDATE_STEMS = ("vocals", "piano", "guitar", "other")


def _rms(wav: Path) -> float:
    audio, _ = sf.read(wav)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    if audio.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(audio))))


def rank_stems(stems: dict[str, Path]) -> list[tuple[str, float]]:
    """All stems ranked by RMS energy, descending: [(name, rms), ...]."""
    return sorted(((name, _rms(p)) for name, p in stems.items()),
                  key=lambda kv: kv[1], reverse=True)


def suggest_stem(stems: dict[str, Path]) -> str:
    """The highest-energy melodic candidate stem (falls back to overall loudest)."""
    energies = {name: _rms(p) for name, p in stems.items()}
    candidates = [n for n in CANDIDATE_STEMS if n in energies]
    pool = candidates or list(energies)
    return max(pool, key=lambda n: energies[n])
