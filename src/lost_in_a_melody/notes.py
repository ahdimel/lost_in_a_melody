"""Note primitives: the canonical Note event + MIDI ↔ note-name ↔ 88-key mapping.

The whole pipeline speaks in `Note` events timed in **seconds** (what was actually
performed). Conversion to tempo-relative **beats** happens only at render time
(see `tempo.py` / `render.py`), per decision D8.

The target instrument is an 88-key piano, A0–C8 == MIDI 21–108 inclusive.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# 88-key range
MIDI_MIN = 21   # A0
MIDI_MAX = 108  # C8

_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
_NAME_RE = re.compile(r"^([A-Ga-g])([#b]?)(-?\d+)$")
_LETTER_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


@dataclass
class Note:
    """A single performed note. Times are absolute **seconds** from clip start."""
    start: float
    end: float
    pitch: int            # MIDI number

    @property
    def duration(self) -> float:
        return self.end - self.start

    @property
    def name(self) -> str:
        return midi_to_name(self.pitch)


def midi_to_name(midi: int) -> str:
    """MIDI number → scientific note name, e.g. 60 → 'C4', 61 → 'C#4'."""
    return f"{_NAMES[midi % 12]}{midi // 12 - 1}"


def name_to_midi(name: str) -> int:
    """Scientific note name → MIDI number. Accepts sharps or flats ('Bb4' == 'A#4')."""
    m = _NAME_RE.match(name.strip())
    if not m:
        raise ValueError(f"unparseable note name: {name!r}")
    letter, accidental, octave = m.group(1).upper(), m.group(2), int(m.group(3))
    pc = _LETTER_PC[letter] + (1 if accidental == "#" else -1 if accidental == "b" else 0)
    return pc + 12 * (octave + 1)


def in_88_key(midi: int) -> bool:
    return MIDI_MIN <= midi <= MIDI_MAX


def clamp_to_88(midi: int) -> int:
    """Fold an out-of-range pitch into the 88-key range by whole octaves."""
    while midi < MIDI_MIN:
        midi += 12
    while midi > MIDI_MAX:
        midi -= 12
    return midi
