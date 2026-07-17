# Lost in a Melody — Project Handoff

> A local tool that turns a short song clip into a beginner-friendly, play-along
> sequence of piano keys — a sequential "which key do I press next" guide for an
> 88-key keyboard, with a Synthesia-style falling-note visualizer.

This document is the single source of truth for picking the project back up. It
captures the goal, every decision made during scoping, the architecture, the data
model, and the phased build plan.

---

## 1. Who this is for / the core problem

The owner plays simple melodies of songs they like on a **Casio Privia PX (88 keys,
A0–C8)** but is **not musically educated and cannot read sheet music**. Visual
guides like [Hooktheory](https://www.hooktheory.com/) are great but only exist for
some songs. This tool generates that same "sequence of keys + rough timing" guide
for **any** short audio clip, locally.

The owner acts as the **feedback/correction loop by ear** — the tool only needs to
be "good enough," not perfect. Correcting a wrong note is expected and must be cheap
(edit a text file).

---

## 2. Scope

### In scope
- **Input**: a local audio file, OR a URL (YouTube etc.) fetched to audio.
- **Clip**: trim to a short segment (~5–30s for MVP; longer later).
- **Extract the melody** from a full mix ("whatever carries the tune").
- **Transcribe** to timed note events in **two flavors, both always computed**:
  - **Melody line (mono)** — clean, one-note-at-a-time.
  - **Full transcription (poly)** — all detected notes, may include chords.
- **Output**:
  - MVP: a human-readable, hand-editable note list + a static piano-roll image.
  - Phase 2: a GUI with a Synthesia-style falling-note player over an 88-key
    keyboard.
- **Local library** of clips and their processed outputs.
- **Fully local. Nothing leaves the machine.**

### Explicitly out of scope (for now)
- Perfect/automatic transcription. Owner corrects by ear.
- Curated chord charts like Hooktheory's clean `I–IV` track. Our "poly" is raw
  transcription, not music-theory-labeled chords.
- Sheet-music notation output.
- Cloud/hosted anything.

---

## 3. Decisions locked during scoping

| # | Decision | Value |
|---|----------|-------|
| D1 | Input clips are short | ~5–30s MVP; trivially expandable |
| D2 | Accuracy bar | "Good enough" + cheap manual correction |
| D3 | Correction mechanism | Edit a plain-text `notes.txt` file |
| D4 | Melody source | "Whatever carries the tune" = pick a Demucs stem |
| D5 | Locality | 100% local; a **local library** of clips + outputs |
| D6 | Mono vs poly | Compute **both**, toggle to switch after processing |
| D7 | `.gitignore` policy | Commit only small text (`meta.json`, `notes.txt`); ignore audio/MIDI/PNG |
| D8 | `notes.txt` timing units | **Beats** (tempo-relative), not seconds |
| D9 | Piano sound | **Salamander Grand Piano V3** (CC-BY 3.0) via **Tone.js Sampler** |
| D10 | GUI processing feedback | No real progress bar. Just status text: `processing…` → `done` / `error`, persisted until next action, plus a **KILL** button if stuck |
| D11 | GUI architecture | Local **FastAPI backend** + browser frontend (browser can't run the ML) |
| D12 | Simplified audio | Synthesized **in the browser** (Tone.js) so it shares one clock with the animation |

---

## 4. The pipeline (five stages)

```
URL / file
   │  (1) ACQUIRE      yt-dlp + ffmpeg  → normalized clip.wav (trimmed to start/end)
   ▼
clip.wav
   │  (2) SEPARATE     Demucs (htdemucs) → stems/{vocals,drums,bass,other}.wav
   ▼
stems/
   │  (3) PICK STEM    suggest tune-carrier (score) + owner override
   ▼
chosen stem
   │  (4) TRANSCRIBE   ├─ mono: torchcrepe → f0 → note segmentation → melody_mono
   │                   └─ poly: Basic Pitch (ONNX) → MIDI            → melody_poly
   ▼
note events
   │  (5) RENDER       librosa beat grid → quantize → notes.json / notes.txt / pianoroll.png
   ▼
outputs (+ Phase-2 falling-note viewer)
```

### Why these tools
- **yt-dlp + ffmpeg** — fetch + trim/normalize to WAV. `ffmpeg` is a system binary
  (`brew install ffmpeg`).
- **Demucs (`htdemucs`)** — SOTA source separation; runs on Apple Silicon (MPS/CPU).
  Gives 4 stems; `other` holds non-vocal melodic content (lead guitar/synth/piano).
- **Basic Pitch (ONNX backend)** — audio→MIDI in one call. **ONNX backend chosen to
  avoid TensorFlow-on-macOS dependency pain.**
- **torchcrepe** — monophonic f0 tracker. **Chosen over Google CREPE to stay on
  PyTorch** (already pulled in by Demucs) and dodge a TF dependency conflict.
- **librosa** — beat tracking → BPM + beat grid for quantization.
- **pretty_midi** — MIDI read/write, note-name & 88-key mapping.

### Picking a stem (D4) — what it actually means
Demucs emits **four ordinary audio files**. "Picking a stem" = **listen and choose
which file carries the tune**, then type its name. Three layers:
1. **Default** `vocals`.
2. **Auto-suggest**: score each stem by sustained, confident, mid-range pitched
   content; recommend the likely tune-carrier.
3. **Override**: set `stem` in `meta.json` and re-run **only** transcription
   (separation is cached, so it's fast).

---

## 5. Repository / data architecture

```
lost_in_a_melody/
├── HANDOFF.md                 # this file
├── README.md
├── pyproject.toml             # deps + `lam` CLI entrypoint
├── .gitignore                 # ignore big binaries; commit small text
├── src/lost_in_a_melody/
│   ├── acquire.py             # yt-dlp + ffmpeg → normalized, trimmed clip.wav
│   ├── separate.py            # Demucs wrapper → stems/
│   ├── suggest_stem.py        # score stems, recommend the tune-carrier
│   ├── transcribe_poly.py     # Basic Pitch (ONNX) → melody_poly.{mid,json}
│   ├── transcribe_mono.py     # torchcrepe → segmentation → melody_mono.{mid,json}
│   ├── tempo.py               # librosa beat grid + quantize-to-beats
│   ├── notes.py               # MIDI ↔ note names, 88-key (A0–C8) mapping
│   ├── render.py              # notes.json ↔ notes.txt, + pianoroll.png
│   ├── library.py             # clip folders + manifest management
│   ├── pipeline.py            # orchestrates stages 1–5 (shared by CLI + backend)
│   ├── server.py              # FastAPI app wrapping pipeline for the GUI
│   └── cli.py                 # `lam` command entrypoint
├── web/                       # Phase 2 frontend (served by the backend)
│   ├── index.html
│   ├── app.js                 # falling notes, keyboard, controls, toggles
│   ├── vendor/tone.js         # bundled locally (no CDN)
│   └── assets/samples/        # Salamander piano subset (NOT committed; fetched)
├── library/                   # the local data store (one folder per clip)
│   └── <clip_id>/
│       ├── clip.wav           # (ignored) trimmed source
│       ├── meta.json          # (committed) title, source, bpm, key, chosen_stem, transpose, trim
│       ├── stems/*.wav        # (ignored)
│       ├── melody_poly.{mid,json}   # mid ignored; json is the note data
│       ├── melody_mono.{mid,json}
│       ├── notes.txt          # (committed) human-editable "nudge" file
│       └── pianoroll.png      # (ignored) MVP static output
└── tests/
```

**Design principle:** each clip is a **self-contained folder**. `pipeline.py` holds
the real logic; **both** `cli.py` and `server.py` are thin layers over it, so the
CLI (headless) and GUI stay in lockstep.

---

## 6. The editable note format (`notes.txt`) — D3, D8

Canonical hand-editable representation. Deliberately dead-simple whitespace columns,
**timing in beats** so it survives tempo changes:

```
# bpm=120  key=Eb  stem=vocals  mode=mono
# start   length   note
0.0       0.5      Eb4
0.5       0.5      G4
1.0       1.0      Bb4
2.0       0.5      Ab4
```

- `start`, `length` are in **beats** (tempo-relative).
- Edit a pitch, delete a line, or shift a start → run `lam render <clip>` and both
  the piano-roll PNG and the web viewer pick up the change.
- `notes.txt` and `notes.json` are two views of the same data; `render.py` keeps
  them in sync. `notes.txt` is the source of truth after manual edits.

---

## 7. CLI (`lam`) — the headless path

```
lam add <file|--url URL> --name <id> [--bpm N] [--start S --end E]   # register + acquire + trim
lam process <id>                    # separate + suggest stem + BOTH transcriptions + render
lam stem <id> --set other           # override stem, re-transcribe only (uses cached stems)
lam show <id>                       # print the note list
lam render <id>                     # re-render outputs from edited notes.txt
lam gui                             # launch FastAPI backend + open the browser viewer
```

`lam process` runs the full pipeline. Because stems are cached, changing the stem or
nudging notes never re-runs the expensive separation.

---

## 8. Phase 2 GUI

### Architecture (D11)
- **Backend**: FastAPI on `localhost`, launched by `lam gui`. Thin HTTP wrappers
  over `pipeline.py`: `POST /acquire`, `POST /process`, `POST /kill`, `GET /clip/<id>`,
  static file serving for `web/`. **Everything stays local.**
- **Frontend**: browser page talking to the backend. Handles all visualization and
  browser-side audio.

### Flow & controls
1. **Ingest**: a text field to paste a URL + **Fetch** button; and a **Load local
   file** button (navigate to a file).
2. **Trim**: once loaded, a **range selector seek bar** (drag handles) to set
   clip **start/end**.
3. **Process**: a **Process** button kicks off separate+transcribe. Status is
   **plain text only** (D10): `processing…` while running → `done` (persists until
   next action) or `error`. A **KILL** button appears to abort if stuck.
4. **Player** (unlocks when processing is `done`):
   - Full **88-key Canvas keyboard** (A0–C8).
   - **Synthesia-style falling notes** descending onto the keys.
   - **Per-pitch-class color overlay**: map the 12 semitones of one octave to a
     color set, repeat across all octaves; a key lights in its pitch-class color
     when active, and falling notes match.
   - **Play / Pause / Reset** buttons.
   - **Playback scrubber** seek bar (draggable) — *distinct from* the trim bar in
     step 2.
   - **Toggle A — "Melody line" vs "Full transcription"** (= mono vs poly, D6).
   - **Toggle B — "Original song" vs "Simplified"** audio.

### The 2×2 audio/notes logic (agreed)
| Audio source | Effect of the Melody/Full toggle |
|---|---|
| **Original song** | Changes only **which notes are drawn**; audio is the untouched recording |
| **Simplified** | Changes **both** the drawn notes **and** the synthesized audio |

(The "original × mono/poly" distinction is degenerate — the original recording has no
mono/poly version. This is expected and fine.)

### Audio (D9, D12)
- **Original**: play `clip.wav` via a normal audio element.
- **Simplified**: synthesize the MIDI **in the browser** with **Tone.js `Sampler`**
  using **Salamander Grand Piano V3** (Yamaha C5, **CC-BY 3.0**). Ship only a subset
  (~every few semitones); Tone.js pitch-shifts to fill 88 keys. Synthesizing in the
  browser (not a pre-rendered backend WAV) keeps audio and animation on **one clock**.
- Tone.js and the samples are **bundled/downloaded locally** — **no CDN**.
- Samples are large → **not committed**; a setup step downloads them into
  `web/assets/samples/`.
- Fallback (not default): backend synthesis via **FluidSynth + `FluidR3_GM.sf2`**
  (`brew install fluidsynth`) — reintroduces two-clock sync, so avoid unless needed.

### Effort posture
**Function-first, unstyled-but-usable.** No animation polish, theming, or drag-drop
beyond what's listed. The falling-note + colored keyboard is the one place worth real
effort; everything else is minimal.

---

## 9. Environment / setup (macOS, Apple Silicon)

- **Python 3.11** in a project venv (best compat for Demucs / Basic Pitch / torchcrepe).
- System binaries: `brew install ffmpeg` (required), `brew install fluidsynth` (only
  for the fallback synth).
- Python deps (see `pyproject.toml`): `yt-dlp`, `demucs`, `basic-pitch[onnx]`,
  `torchcrepe`, `librosa`, `pretty_midi`, `fastapi`, `uvicorn`, `soundfile`, `numpy`.
- First run downloads model weights (Demucs, Basic Pitch) and the Salamander sample
  subset.

---

## 9b. Apple Silicon / no-Rosetta constraint

**Hard requirement: the entire stack must run natively on Apple Silicon (arm64)
with NO Rosetta.** Apple is winding Rosetta 2 down to a smaller compatibility
subset after macOS 26/27, so nothing here may depend on it.

As scoped, **everything is native arm64.** Two scoping decisions were made
specifically to keep it that way:
- **Basic Pitch on the ONNX backend, not TensorFlow** — `onnxruntime` has arm64
  macOS wheels; `tensorflow-macos` is the classic Rosetta/Apple-Silicon headache.
- **torchcrepe instead of Google CREPE** — stays on PyTorch, avoids a second TF dep.

| Component | Native arm64 | Notes |
|---|---|---|
| Python 3.11 | ✅ | python.org / arm64 Homebrew / miniforge |
| ffmpeg | ✅ | `brew install ffmpeg` |
| PyTorch (`torch`) | ✅ | arm64 wheels + MPS accel; powers Demucs & torchcrepe |
| Demucs, torchcrepe | ✅ | Pure Python on torch |
| Basic Pitch (ONNX) | ✅ | `onnxruntime` arm64 wheels |
| librosa (+ numba/llvmlite, scipy, soundfile) | ✅ | all have arm64 wheels |
| numpy / scipy | ✅ | native wheels |
| pretty_midi, yt-dlp, FastAPI, uvicorn, soundfile | ✅ | pure Python or native libs |
| FluidSynth (fallback only) | ✅ | `brew install fluidsynth` |
| Tone.js + Salamander samples | n/a | browser-side, architecture-independent |

**Install-time hygiene (not design changes):**
- **Keep the Python 3.11 pin.** `numba`/`llvmlite` (via librosa) can lag on the
  newest Python; 3.11 has full arm64 wheel coverage. Avoid bleeding-edge 3.13,
  where you'd risk a source build.
- **Install into an arm64 toolchain** — arm64 Homebrew (`/opt/homebrew`) + arm64
  Python. Sanity checks: `python3 -c "import platform; print(platform.machine())"`
  → `arm64`, and `file $(which ffmpeg)` → `arm64`.

---

## 10. Phased build plan

- **Phase 0 — Feasibility spike (½ day).** One real song: yt-dlp → Demucs →
  Basic Pitch → open the MIDI. Confirms the quality ceiling before building anything.
- **Phase 1 — MVP (headless).** `pipeline.py` + `cli.py`: acquire/trim → separate →
  suggest+pick stem → both transcriptions → beat-quantize → `notes.txt` +
  `pianoroll.png`. Manual correction loop working.
- **Phase 2 — GUI.** FastAPI backend + browser viewer: ingest, trim, process (with
  status text + KILL), 88-key falling-note player, both toggles, Salamander/Tone.js
  audio.

---

## 11. Current status

- Repo initialized on `main`; remote `origin` = `git@github.com:ahdimel/lost_in_a_melody.git`
  (SSH verified). **Nothing pushed yet.**
- This commit contains **planning scaffold only**: `HANDOFF.md`, `README.md`,
  `.gitignore`, `pyproject.toml`, and empty directory placeholders. **No pipeline
  code written yet.**
- **Next action on pickup**: Phase 0 feasibility spike.

## 12. Open questions for later (non-blocking)
- Longer-clip handling (paging the falling-note view / memory for multi-minute audio).
- Key/scale detection to snap corrections to a scale (nice-to-have).
- Whether to expose the auto-suggested stem confidence in the GUI.
```

