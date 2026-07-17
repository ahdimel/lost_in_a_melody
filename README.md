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
Planning scaffold. No pipeline code yet. Next step: Phase 0 feasibility spike
(see HANDOFF §10).

## Stack (planned)
yt-dlp · ffmpeg · Demucs · Basic Pitch (ONNX) · torchcrepe · librosa · pretty_midi ·
FastAPI · Tone.js + Salamander Grand Piano V3
