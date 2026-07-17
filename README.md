# Lost in a Melody

A **fully local** tool that turns a short song clip into a beginner-friendly
play-along guide for an 88-key piano — a "which key do I press next" sequence with
rough timing, plus a Synthesia-style falling-note visualizer.

Built for a keyboard player who can't read sheet music and corrects by ear.

- **Input**: a local audio file, or a URL fetched to audio.
- **Output**: an editable note list + piano-roll (MVP), and a falling-note GUI
  (Phase 2).
- **Two views**: a clean single-note **melody line** and a **full transcription**,
  toggleable.

See **[HANDOFF.md](HANDOFF.md)** for the full design, decisions, architecture, and
build plan.

## Status
**Phase 1 (headless MVP) is complete.** The full pipeline + `lam` CLI work end-to-end;
on a validated test (Scarborough Fair) the melody line matches a Hooktheory reference
29/29 on pitch. **Phase 2 (the falling-note GUI) is next** and not yet built. See
[HANDOFF.md](HANDOFF.md) §11 for exact status and §13 for the Phase 0/1 findings.

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
```
Full CLI in HANDOFF §7. Everything runs **locally** and **native arm64** (no Rosetta).

## Stack
yt-dlp · ffmpeg · Demucs (`htdemucs_6s`) · Basic Pitch (ONNX) · torchcrepe · librosa ·
pretty_midi · matplotlib — and, for Phase 2: FastAPI · Tone.js + Salamander Grand Piano V3
