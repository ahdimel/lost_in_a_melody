"""Stage 2 — SEPARATE: `clip.wav` → 6 stems via Demucs `htdemucs_6s`.

The 6-source model is used (not the default 4-source `htdemucs`) because it emits a
dedicated `piano` and `guitar` stem — Phase 0 showed the 4-source model buries piano
in `other`, which broke tune-carrier picking for piano-driven songs.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

MODEL = "htdemucs_6s"
STEM_NAMES = ("vocals", "drums", "bass", "other", "piano", "guitar")


def separate(clip: Path, stems_dir: Path, *, force: bool = False) -> dict[str, Path]:
    """Separate `clip` into stems under `stems_dir/`. Returns {stem_name: wav_path}.

    Separation is cached: if the stems already exist and `force` is False, Demucs is
    skipped (this is what makes re-picking a stem / re-transcribing cheap, per D4/§7).
    """
    stems_dir.mkdir(parents=True, exist_ok=True)
    existing = {p.stem: p for p in stems_dir.glob("*.wav")}
    if not force and all(name in existing for name in STEM_NAMES):
        return {name: existing[name] for name in STEM_NAMES}

    # Demucs writes to <out>/<model>/<clip_stem>/<name>.wav; collect from there.
    out_root = stems_dir / "_demucs"
    subprocess.run(
        [sys.executable, "-m", "demucs", "-n", MODEL, "-o", str(out_root), str(clip)],
        check=True,
    )
    produced = out_root / MODEL / clip.stem
    result: dict[str, Path] = {}
    for name in STEM_NAMES:
        src = produced / f"{name}.wav"
        dest = stems_dir / f"{name}.wav"
        dest.write_bytes(src.read_bytes())
        result[name] = dest
    shutil.rmtree(out_root, ignore_errors=True)  # drop the duplicate demucs tree
    return result
