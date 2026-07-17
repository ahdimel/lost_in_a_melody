"""Fetch a subset of the Salamander Grand Piano V3 samples (CC-BY 3.0) for the
Phase-2 browser player (D9).

Tone.js's `Sampler` pitch-shifts to fill all 88 keys, so we only ship one sample
every minor third (A, C, D#, F#) — the classic Tone.js Salamander subset. The files
are large, so they are **git-ignored** and downloaded on demand by `lam fetch-samples`.
The player degrades to a plain Tone.js synth if they are absent, so this is optional.
"""
from __future__ import annotations

import urllib.request
from pathlib import Path
from typing import Callable

BASE_URL = "https://tonejs.github.io/audio/salamander"

# Note names Tone.js's Sampler keys on → the sample filenames on the CDN.
# The pack provides one sample every minor third from A0 to C8.
_PITCHES = ["A", "C", "D#", "F#"]


def _build_map() -> dict[str, str]:
    out: dict[str, str] = {}
    # A0 first (its octave only has A), then C1..F#7 by octave, then C8 last.
    out["A0"] = "A0.mp3"
    for octave in range(1, 8):
        for pitch in _PITCHES:
            name = f"{pitch}{octave}"
            out[name] = name.replace("#", "s") + ".mp3"
    out["C8"] = "C8.mp3"
    return out


SALAMANDER: dict[str, str] = _build_map()

Log = Callable[[str], None]


def sample_dir(web_root: Path) -> Path:
    return web_root / "assets" / "samples"


def have_samples(web_root: Path) -> bool:
    """True once the full subset is present (used to pick Sampler vs synth)."""
    d = sample_dir(web_root)
    return all((d / fn).exists() for fn in SALAMANDER.values())


def fetch_salamander(web_root: Path, *, log: Log = print) -> Path:
    """Download the Salamander subset into web/assets/samples/. Idempotent."""
    dest = sample_dir(web_root)
    dest.mkdir(parents=True, exist_ok=True)
    total = len(SALAMANDER)
    for i, filename in enumerate(sorted(set(SALAMANDER.values())), 1):
        target = dest / filename
        if target.exists() and target.stat().st_size > 0:
            log(f"[{i}/{total}] have {filename}")
            continue
        url = f"{BASE_URL}/{filename}"
        log(f"[{i}/{total}] fetch {filename}")
        urllib.request.urlretrieve(url, target)
    log(f"samples ready → {dest}")
    return dest
