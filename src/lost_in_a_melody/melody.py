"""Stage 4b — MELODY: skim a single-line play-along melody off the poly transcription.

Phase 0 validated this as THE melody method (it matched a Hooktheory ground truth
29/29 and beat torchcrepe even on a monophonic vocal): the melody is the **highest
active note over time**.

The subtlety that earned its own fix: preserve **note identity / onsets** so repeated
notes survive. We don't segment by pitch (which merges "C C C" into one held C); we
segment by *which underlying poly note* is currently on top. Two separate strikes of
the same pitch are different `Note` objects with different winning windows, so they
stay two melody notes — exactly what a play-along needs ("press the key 3 times").
"""
from __future__ import annotations

import numpy as np

from .notes import Note

GRID = 0.01        # 10 ms sampling of the "who is on top" function
MIN_DUR = 0.08     # drop a melody note that is the top voice for < 80 ms (flicker)
MERGE_GAP = 0.06   # merge same-pitch notes whose winning windows nearly abut


def extract_melody(poly: list[Note], *, grid: float = GRID, min_dur: float = MIN_DUR,
                   merge_gap: float = MERGE_GAP) -> list[Note]:
    """Highest-active-note melody line, onset-preserving and monophonic.

    `merge_gap` heals Basic Pitch's over-splitting of *sustained* notes: consecutive
    same-pitch notes whose winning windows nearly abut (a split sustain) are merged,
    while same-pitch notes separated by a clear gap (a deliberate repeat) are kept.
    Set `merge_gap=0` to disable and keep every onset (most faithful).
    """
    if not poly:
        return []
    end = max(n.end for n in poly)
    frames = np.arange(0.0, end, grid)
    # winner[k] = index of the highest-pitch note active at frames[k], or -1
    winner = np.full(len(frames), -1, dtype=int)
    for k, t in enumerate(frames):
        best_idx, best_pitch = -1, -1
        for i, n in enumerate(poly):
            if n.start <= t < n.end and n.pitch > best_pitch:
                best_idx, best_pitch = i, n.pitch
        winner[k] = best_idx

    # each poly note that ever wins → one melody note spanning its winning window
    mel: list[Note] = []
    for i, n in enumerate(poly):
        won = np.flatnonzero(winner == i)
        if won.size == 0:
            continue
        start = frames[won[0]]
        stop = frames[won[-1]] + grid
        if stop - start >= min_dur:
            mel.append(Note(start=float(start), end=float(stop), pitch=n.pitch))

    mel.sort(key=lambda n: n.start)

    # heal split sustains: merge same-pitch notes whose winning windows nearly abut
    merged: list[Note] = []
    for n in mel:
        prev = merged[-1] if merged else None
        if prev and prev.pitch == n.pitch and n.start - prev.end <= merge_gap:
            prev.end = n.end
        else:
            merged.append(n)

    # keep it strictly monophonic: never let one note bleed past the next onset
    for a, b in zip(merged, merged[1:]):
        if a.end > b.start:
            a.end = b.start
    return [n for n in merged if n.end - n.start >= min_dur]
