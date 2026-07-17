"""Stage 4a — POLY transcription: stem WAV → full note events via Basic Pitch (ONNX).

Returns every detected note as a `Note` (seconds). This is both the "full
transcription" flavor (D6) *and* the raw material the melody extractor skims the top
line off of. We deliberately keep Basic Pitch's individual note onsets untouched —
Phase 0 showed that merging same-pitch notes destroys repeated-note rhythm.
"""
from __future__ import annotations

from pathlib import Path

from .notes import Note, clamp_to_88, in_88_key


def transcribe_poly(stem_wav: Path) -> list[Note]:
    """Basic Pitch (ONNX backend) → list of `Note`, sorted by start time.

    Notes outside the 88-key range are folded into it by whole octaves (rare; usually
    sub-bass artifacts). Basic Pitch is imported lazily so the rest of the package
    (and the CLI's --help) doesn't pay its heavy import cost.
    """
    from basic_pitch.inference import predict  # lazy: heavy ONNX/onnxruntime import

    _model_output, midi, _note_events = predict(str(stem_wav))
    notes: list[Note] = []
    for inst in midi.instruments:
        for n in inst.notes:
            pitch = int(n.pitch)
            pitch = pitch if in_88_key(pitch) else clamp_to_88(pitch)
            notes.append(Note(start=float(n.start), end=float(n.end), pitch=pitch))
    notes.sort(key=lambda n: (n.start, n.pitch))
    return notes
