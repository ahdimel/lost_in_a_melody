"""Orchestrates stages 1–5. The real logic lives here; `cli.py` and (Phase 2)
`server.py` are thin layers over these functions so headless and GUI stay in lockstep.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from . import acquire as _acquire
from . import separate as _separate
from . import suggest_stem as _suggest
from . import tempo as _tempo
from . import render as _render
from .melody import extract_melody
from .transcribe_poly import transcribe_poly
from .library import Library, Clip

Log = Callable[[str], None]


def add(lib: Library, clip_id: str, source: str, *, is_url: bool,
        start: float | None = None, end: float | None = None,
        bpm: float | None = None, title: str = "", log: Log = print) -> Clip:
    """Stage 1: register a clip and acquire/trim its audio."""
    clip = lib.register(clip_id, source, is_url=is_url, title=title,
                        trim_start=start, trim_end=end, bpm=bpm)
    log(f"acquiring → {clip.clip_wav}")
    _acquire.acquire(source, clip.clip_wav, is_url=is_url, start=start, end=end)
    log("acquired.")
    return clip


def process(lib: Library, clip_id: str, *, stem_override: str | None = None,
            quantize: float | None = _tempo.DEFAULT_GRID,
            force_separate: bool = False, log: Log = print) -> Clip:
    """Stages 2–5: separate → pick stem → poly + melody → beats → all artifacts."""
    clip = lib.clip(clip_id)
    meta = clip.load_meta()
    if not clip.clip_wav.exists():
        raise FileNotFoundError(f"{clip.id}: no clip.wav — run `add` first")

    log("separating (Demucs htdemucs_6s)…")
    stems = _separate.separate(clip.clip_wav, clip.stems_dir, force=force_separate)

    ranking = _suggest.rank_stems(stems)
    log("stem energy: " + ", ".join(f"{n}={r:.4f}" for n, r in ranking))
    stem = stem_override or _suggest.suggest_stem(stems)
    meta.stem = stem
    log(f"tune-carrier stem = {stem}")

    log("transcribing (Basic Pitch, ONNX)…")
    poly = transcribe_poly(stems[stem])
    mel = extract_melody(poly)
    log(f"poly={len(poly)} notes, melody={len(mel)} notes")

    if meta.bpm is None:
        meta.bpm = _tempo.detect_bpm(clip.clip_wav)
    log(f"bpm = {meta.bpm}")

    _write_outputs(clip, meta, poly, mel, quantize)
    meta.mode = "melody"
    clip.save_meta(meta)
    log(f"done → {clip.dir}")
    return clip


def set_stem(lib: Library, clip_id: str, stem: str, *,
             quantize: float | None = _tempo.DEFAULT_GRID, log: Log = print) -> Clip:
    """Override the stem and re-transcribe only (cached stems ⇒ no re-separation)."""
    clip = lib.clip(clip_id)
    if not clip.stems_dir.exists():
        raise FileNotFoundError(f"{clip.id}: no stems — run `process` first")
    return process(lib, clip_id, stem_override=stem, quantize=quantize,
                   force_separate=False, log=log)


def render(lib: Library, clip_id: str, *, log: Log = print) -> Clip:
    """Re-derive melody.json / melody.mid / pianoroll.png from an edited notes.txt."""
    clip = lib.clip(clip_id)
    if not clip.notes_txt.exists():
        raise FileNotFoundError(f"{clip.id}: no notes.txt — run `process` first")
    header, beatnotes = _render.read_notes_txt(clip.notes_txt)
    meta = clip.load_meta()
    bpm = float(header.get("bpm", meta.bpm or 120.0))
    stem = header.get("stem", meta.stem or "?")
    mode = header.get("mode", meta.mode)
    key = header.get("key") if header.get("key") not in (None, "?") else meta.key

    _render.write_notes_json(clip.artifact("melody.json"), beatnotes,
                             bpm=bpm, stem=stem, mode=mode, key=key)
    _render.write_midi(clip.artifact("melody.mid"),
                       _render.beatnotes_to_seconds(beatnotes, bpm))
    _render.render_pianoroll(clip.pianoroll, beatnotes, title=f"{clip.id} — {mode}")
    log(f"re-rendered from notes.txt → {clip.dir}")
    return clip


# ── internal ────────────────────────────────────────────────────────────────
def _write_outputs(clip: Clip, meta, poly, mel, quantize) -> None:
    bpm, stem = meta.bpm, meta.stem
    mel_beats = _tempo.to_beats(mel, bpm, quantize=quantize)
    poly_beats = _tempo.to_beats(poly, bpm, quantize=quantize)

    # play-along melody line (the editable, primary output)
    _render.write_notes_txt(clip.notes_txt, mel_beats, bpm=bpm, stem=stem,
                            mode="melody", key=meta.key)
    _render.write_notes_json(clip.artifact("melody.json"), mel_beats, bpm=bpm,
                             stem=stem, mode="melody", key=meta.key)
    _render.write_midi(clip.artifact("melody.mid"), mel)

    # full transcription (the "Full" toggle flavor)
    _render.write_notes_json(clip.artifact("poly.json"), poly_beats, bpm=bpm,
                             stem=stem, mode="poly", key=meta.key)
    _render.write_midi(clip.artifact("poly.mid"), poly)

    _render.render_pianoroll(clip.pianoroll, mel_beats, title=f"{clip.id} — melody")
