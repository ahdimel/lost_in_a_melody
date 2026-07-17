"""Pure-logic tests for the parts most likely to regress. No ML / no network."""
from pathlib import Path

from lost_in_a_melody.notes import (
    Note, midi_to_name, name_to_midi, in_88_key, clamp_to_88, MIDI_MIN, MIDI_MAX,
)
from lost_in_a_melody.melody import extract_melody
from lost_in_a_melody.tempo import to_beats
from lost_in_a_melody import render


# ── note name ↔ MIDI ─────────────────────────────────────────────────────────
def test_name_midi_roundtrip():
    for midi in range(MIDI_MIN, MIDI_MAX + 1):
        assert name_to_midi(midi_to_name(midi)) == midi

def test_known_names():
    assert midi_to_name(60) == "C4"
    assert name_to_midi("A0") == 21 and name_to_midi("C8") == 108
    assert name_to_midi("Bb4") == name_to_midi("A#4")  # flats accepted

def test_88_key_bounds_and_clamp():
    assert in_88_key(21) and in_88_key(108)
    assert not in_88_key(20) and not in_88_key(109)
    assert MIDI_MIN <= clamp_to_88(12) <= MIDI_MAX     # sub-bass folds up
    assert MIDI_MIN <= clamp_to_88(120) <= MIDI_MAX    # too-high folds down


# ── melody extraction: the onset-preservation guarantee ──────────────────────
def test_repeated_notes_survive():
    # three separate strikes of the same pitch must stay three melody notes
    poly = [Note(0.0, 0.4, 60), Note(0.5, 0.9, 60), Note(1.0, 1.4, 60)]
    mel = extract_melody(poly)
    assert [n.pitch for n in mel] == [60, 60, 60]

def test_top_line_wins_over_lower():
    # a higher note overlapping a lower one → melody takes the higher pitch
    poly = [Note(0.0, 1.0, 55), Note(0.2, 0.8, 67)]
    mel = extract_melody(poly)
    assert 67 in [n.pitch for n in mel]

def test_monophonic_output():
    poly = [Note(0.0, 1.0, 60), Note(0.5, 1.5, 64)]
    mel = extract_melody(poly)
    for a, b in zip(mel, mel[1:]):
        assert a.end <= b.start + 1e-9


# ── tempo → beats ────────────────────────────────────────────────────────────
def test_to_beats_scaling_and_floor():
    notes = [Note(0.0, 0.5, 60)]           # at 120 bpm, 0.5 s == 1 beat
    (start, length, pitch), = to_beats(notes, 120.0, quantize=0.25)
    assert start == 0.0 and length == 1.0 and pitch == 60
    # a very short note keeps at least one grid unit (never vanishes)
    (_, tiny_len, _), = to_beats([Note(0.0, 0.01, 60)], 120.0, quantize=0.25)
    assert tiny_len == 0.25


# ── notes.txt round-trip (the correction loop) ───────────────────────────────
def test_notes_txt_roundtrip(tmp_path: Path):
    beats = [(0.0, 1.0, 60), (1.0, 0.5, 64), (1.5, 2.0, 67)]
    p = tmp_path / "notes.txt"
    render.write_notes_txt(p, beats, bpm=120, stem="vocals", mode="melody", key="C")
    header, parsed = render.read_notes_txt(p)
    assert header["bpm"] == "120" and header["stem"] == "vocals"
    assert parsed == beats
