# Lost in a Melody

A **fully local** tool that turns a short song clip into a beginner-friendly
play-along guide for an 88-key piano — a "which key do I press next" sequence with
rough timing, plus a Synthesia-style falling-note visualizer.

Built for a keyboard player who can't read sheet music and corrects by ear.

- **Input**: a local audio file, or a URL fetched to audio.
- **Output**: an editable note list + piano-roll (CLI), and a Synthesia-style
  falling-note GUI over a full 88-key keyboard.
- **Two views**: a clean single-note **melody line** and a **full transcription**,
  toggleable — with **Original** vs browser-synthesized **Simplified** audio.

See **[HANDOFF.md](HANDOFF.md)** for the full design, decisions, architecture, and
build plan.

## Status
**Phases 0–2 are complete.** The headless pipeline + `lam` CLI work end-to-end (on a
validated test, Scarborough Fair, the melody line matches a Hooktheory reference 29/29
on pitch), and the **Phase 2 browser GUI is built and verified**: ingest → drag-trim →
process (with status text + a KILL button), then a falling-note player with per-pitch-class
colors and active-key highlighting. 17 tests pass. See [HANDOFF.md](HANDOFF.md) §11.

## Quickstart (macOS, Apple Silicon)
```bash
brew install ffmpeg
cd lost_in_a_melody
/opt/homebrew/bin/python3.10 -m venv .venv
./.venv/bin/python -m pip install -U pip && ./.venv/bin/python -m pip install -e .

# fetch + trim a clip, then transcribe it
./.venv/bin/lam add --url "<youtube-url>" --name mysong --start 9 --end 41
./.venv/bin/lam process mysong        # → library/mysong/notes.txt + pianoroll.png + MIDI

./.venv/bin/lam show mysong           # read the melody
# correct any wrong notes by ear in notes.txt, then:
./.venv/bin/lam render mysong

# …or drive the whole thing from the browser:
./.venv/bin/lam gui                   # opens http://127.0.0.1:8765
./.venv/bin/lam fetch-samples         # optional: real Salamander piano for "Simplified"
```
Full CLI in HANDOFF §7. Everything runs **locally** and **native arm64** (no Rosetta);
Tone.js is vendored (no CDN), and the piano samples download on demand.

## Stack
yt-dlp · ffmpeg · Demucs (`htdemucs_6s`) · Basic Pitch (ONNX) · torchcrepe · librosa ·
pretty_midi · matplotlib · FastAPI + uvicorn · Tone.js + Salamander Grand Piano V3
