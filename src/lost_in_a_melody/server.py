"""Phase 2 GUI backend — a thin FastAPI layer over `pipeline.py` (D11).

Everything stays local. The browser can't run the ML, so the heavy stages run here:
  - fast/quick work (ingest, trim, reading artifacts) runs in-process,
  - the slow, killable stage (`lam process` = separate + transcribe + render) runs as
    a **subprocess of our own CLI**, so a KILL can actually terminate it (D10) and the
    headless and GUI paths stay in lockstep by construction.

At most one job runs at a time; the frontend polls `GET /api/job` for status text and
the accumulated log, and hits `POST /api/kill` to abort.
"""
from __future__ import annotations

import subprocess
import sys
import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import pipeline
from . import samples as _samples
from .library import Library

WEB_ROOT = Path(__file__).resolve().parents[2] / "web"


# ── the single-job model ─────────────────────────────────────────────────────
class Job:
    """The one background job (if any). Runs a `lam` subprocess we can kill."""

    def __init__(self) -> None:
        self.kind: str = ""            # "process" (the slow one)
        self.clip_id: str = ""
        self.state: str = "idle"       # idle | running | done | error
        self.log: list[str] = []
        self._proc: subprocess.Popen | None = None
        self._lock = threading.Lock()

    def snapshot(self) -> dict:
        with self._lock:
            return {"kind": self.kind, "id": self.clip_id,
                    "state": self.state, "log": list(self.log)}

    def running(self) -> bool:
        return self.state == "running"

    def start(self, kind: str, clip_id: str, argv: list[str]) -> None:
        with self._lock:
            if self.state == "running":
                raise RuntimeError("a job is already running")
            self.kind, self.clip_id, self.state, self.log = kind, clip_id, "running", []
        threading.Thread(target=self._run, args=(argv,), daemon=True).start()

    def _run(self, argv: list[str]) -> None:
        try:
            proc = subprocess.Popen(argv, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, text=True, bufsize=1)
        except Exception as exc:  # spawn failure
            with self._lock:
                self.log.append(f"failed to start: {exc}")
                self.state = "error"
            return
        with self._lock:
            self._proc = proc
        assert proc.stdout is not None
        for line in proc.stdout:
            with self._lock:
                self.log.append(line.rstrip("\n"))
        proc.wait()
        with self._lock:
            killed = self.state == "error"  # KILL set error already
            if not killed:
                self.state = "done" if proc.returncode == 0 else "error"
                if proc.returncode != 0:
                    self.log.append(f"exited with code {proc.returncode}")
            self._proc = None

    def kill(self) -> bool:
        with self._lock:
            proc = self._proc
            if proc is None or self.state != "running":
                return False
            self.state = "error"
            self.log.append("KILLED by user")
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        return True


# ── request bodies ───────────────────────────────────────────────────────────
class IngestBody(BaseModel):
    name: str
    url: str | None = None
    path: str | None = None      # local file path (server-side)


class ProcessBody(BaseModel):
    id: str
    start: float | None = None
    end: float | None = None
    stem: str | None = None
    quantize: bool = True


# ── app factory ──────────────────────────────────────────────────────────────
def create_app(library_root: str | Path = "library") -> FastAPI:
    app = FastAPI(title="Lost in a Melody")
    lib = Library(Path(library_root).expanduser())
    job = Job()

    def _lam_argv(*args: str) -> list[str]:
        return [sys.executable, "-m", "lost_in_a_melody.cli",
                "--library", str(lib.root), *args]

    # ---- status / library -------------------------------------------------
    @app.get("/api/status")
    def status() -> dict:
        return {"library": str(lib.root),
                "have_samples": _samples.have_samples(WEB_ROOT)}

    @app.get("/api/clips")
    def clips() -> list[dict]:
        out = []
        for cid in lib.list_clips():
            meta = lib.clip(cid).load_meta()
            out.append({"id": cid, "title": meta.title,
                        "stem": meta.stem, "bpm": meta.bpm,
                        "processed": lib.clip(cid).notes_txt.exists()})
        return out

    @app.get("/api/clip/{clip_id}")
    def clip(clip_id: str) -> dict:
        c = lib.clip(clip_id)
        if not c.exists():
            raise HTTPException(404, f"no such clip: {clip_id}")
        meta = c.load_meta()
        payload: dict = {"meta": {"id": c.id, "title": meta.title, "bpm": meta.bpm,
                                  "key": meta.key, "stem": meta.stem,
                                  "trim_start": meta.trim_start,
                                  "trim_end": meta.trim_end},
                         "processed": c.notes_txt.exists()}
        if c.source_wav.exists():
            payload["source_duration"] = pipeline.audio_duration(c.source_wav)
            payload["has_source"] = True
        payload["has_clip"] = c.clip_wav.exists()
        import json  # read the (small) note JSONs inline
        for flavor in ("melody", "poly"):
            f = c.artifact(f"{flavor}.json")
            payload[flavor] = json.loads(f.read_text()) if f.exists() else None
        return payload

    @app.get("/api/clip/{clip_id}/source")
    def clip_source(clip_id: str) -> FileResponse:
        c = lib.clip(clip_id)
        if not c.source_wav.exists():
            raise HTTPException(404, "no source audio")
        return FileResponse(c.source_wav, media_type="audio/wav")

    @app.get("/api/clip/{clip_id}/audio")
    def clip_audio(clip_id: str) -> FileResponse:
        c = lib.clip(clip_id)
        target = c.clip_wav if c.clip_wav.exists() else c.source_wav
        if not target.exists():
            raise HTTPException(404, "no audio")
        return FileResponse(target, media_type="audio/wav")

    # ---- actions ----------------------------------------------------------
    @app.post("/api/ingest")
    def ingest(body: IngestBody) -> dict:
        if job.running():
            raise HTTPException(409, "a job is already running")
        if not body.url and not body.path:
            raise HTTPException(400, "provide url or path")
        is_url = bool(body.url)
        source = body.url or body.path or ""
        try:
            c = pipeline.ingest(lib, body.name, source, is_url=is_url,
                                title=body.name, log=lambda _m: None)
        except Exception as exc:
            raise HTTPException(400, f"ingest failed: {exc}")
        return {"id": c.id, "duration": pipeline.audio_duration(c.source_wav)}

    @app.post("/api/process")
    def process(body: ProcessBody) -> dict:
        c = lib.clip(body.id)
        if not c.exists():
            raise HTTPException(404, f"no such clip: {body.id}")
        # commit the trim in-process (fast), then hand the slow work to a subprocess.
        try:
            pipeline.trim_clip(lib, body.id, start=body.start, end=body.end,
                               log=lambda _m: None)
        except Exception as exc:
            raise HTTPException(400, f"trim failed: {exc}")
        args = ["process", c.id]
        if body.stem:
            args += ["--stem", body.stem]
        if not body.quantize:
            args += ["--no-quantize"]
        try:
            job.start("process", c.id, _lam_argv(*args))
        except RuntimeError as exc:
            raise HTTPException(409, str(exc))
        return {"state": "running", "id": c.id}

    @app.get("/api/job")
    def job_status() -> dict:
        return job.snapshot()

    @app.post("/api/kill")
    def kill() -> dict:
        return {"killed": job.kill()}

    # ---- static frontend (mounted last so /api/* wins) --------------------
    if WEB_ROOT.exists():
        app.mount("/", StaticFiles(directory=str(WEB_ROOT), html=True), name="web")
    return app


def serve(library_root: str | Path = "library", *, host: str = "127.0.0.1",
          port: int = 8765, open_browser: bool = True) -> None:
    import uvicorn

    if open_browser:
        import threading
        import webbrowser

        threading.Timer(1.0, lambda: webbrowser.open(f"http://{host}:{port}")).start()
    uvicorn.run(create_app(library_root), host=host, port=port, log_level="info")
