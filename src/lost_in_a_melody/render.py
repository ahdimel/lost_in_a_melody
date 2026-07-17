"""Stage 5b — RENDER: turn beat-timed notes into the project's output artifacts.

`notes.txt` (hand-editable, D3) and `notes.json` are two views of the same data;
after a manual edit, `notes.txt` is the source of truth (`lam render` re-derives the
rest from it). Also writes a `.mid` (real seconds, for listening) and `pianoroll.png`.
"""
from __future__ import annotations

import json
from pathlib import Path

from .notes import Note, name_to_midi, midi_to_name
from .tempo import BeatNote

_HEADER = "# start   length   note"


# ── notes.txt ────────────────────────────────────────────────────────────────
def write_notes_txt(path: Path, beatnotes: list[BeatNote], *, bpm: float,
                    stem: str, mode: str, key: str | None = None) -> None:
    lines = [f"# bpm={bpm:g}  key={key or '?'}  stem={stem}  mode={mode}", _HEADER]
    for start, length, pitch in beatnotes:
        lines.append(f"{start:<9.2f}{length:<9.2f}{midi_to_name(pitch)}")
    path.write_text("\n".join(lines) + "\n")


def read_notes_txt(path: Path) -> tuple[dict, list[BeatNote]]:
    """Parse an edited notes.txt → (header dict, beatnotes). Blank/`#` lines ignored."""
    header: dict = {}
    beatnotes: list[BeatNote] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("#"):
            for tok in line.lstrip("#").split():
                if "=" in tok:
                    k, v = tok.split("=", 1)
                    header[k] = v
            continue
        parts = line.split()
        if len(parts) < 3:
            continue
        start, length, name = float(parts[0]), float(parts[1]), parts[2]
        beatnotes.append((start, length, name_to_midi(name)))
    return header, beatnotes


# ── notes.json ───────────────────────────────────────────────────────────────
def write_notes_json(path: Path, beatnotes: list[BeatNote], *, bpm: float,
                     stem: str, mode: str, key: str | None = None) -> None:
    data = {
        "bpm": bpm, "key": key, "stem": stem, "mode": mode,
        "notes": [
            {"start": s, "length": length, "pitch": p, "name": midi_to_name(p)}
            for s, length, p in beatnotes
        ],
    }
    path.write_text(json.dumps(data, indent=2) + "\n")


# ── MIDI (real seconds, for listening) ───────────────────────────────────────
def beatnotes_to_seconds(beatnotes: list[BeatNote], bpm: float) -> list[Note]:
    spb = 60.0 / bpm
    return [Note(start=s * spb, end=(s + length) * spb, pitch=p)
            for s, length, p in beatnotes]


def write_midi(path: Path, notes: list[Note], *, program: int = 0) -> None:
    import pretty_midi  # lazy

    pm = pretty_midi.PrettyMIDI()
    inst = pretty_midi.Instrument(program=program)
    for n in notes:
        inst.notes.append(pretty_midi.Note(velocity=96, pitch=n.pitch,
                                            start=n.start, end=max(n.end, n.start + 1e-3)))
    pm.instruments.append(inst)
    pm.write(str(path))


# ── pianoroll.png ────────────────────────────────────────────────────────────
def render_pianoroll(path: Path, beatnotes: list[BeatNote], *, title: str = "") -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(max(6, len(beatnotes) * 0.25), 4))
    for start, length, pitch in beatnotes:
        ax.barh(pitch, length, left=start, height=0.8,
                color="#4c78a8", edgecolor="#28405a")
    if beatnotes:
        pitches = [p for _, _, p in beatnotes]
        lo, hi = min(pitches) - 2, max(pitches) + 2
        ax.set_ylim(lo, hi)
        ax.set_yticks(range(lo, hi + 1))
        ax.set_yticklabels([midi_to_name(m) for m in range(lo, hi + 1)], fontsize=7)
    ax.set_xlabel("beats")
    ax.set_title(title or "melody")
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
