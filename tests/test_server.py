"""Backend tests for the Phase-2 GUI. No ML / no network: the killable job runs a
trivial Python subprocess, not the real `lam process`."""
import sys
import time
from pathlib import Path

from fastapi.testclient import TestClient

from lost_in_a_melody import samples
from lost_in_a_melody.server import create_app, Job


# ── Salamander sample map ─────────────────────────────────────────────────────
def test_salamander_map_endpoints():
    m = samples.SALAMANDER
    # A0 … C8 anchors present, sharps use the "s" filename convention Tone.js expects
    assert m["A0"] == "A0.mp3" and m["C8"] == "C8.mp3"
    assert m["D#1"] == "Ds1.mp3" and m["F#7"] == "Fs7.mp3"
    # one sample every minor third: 1 (A0) + 7*4 + 1 (C8) = 30
    assert len(m) == 30


# ── HTTP surface ──────────────────────────────────────────────────────────────
def _client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(library_root=tmp_path))


def test_status_and_empty_library(tmp_path):
    c = _client(tmp_path)
    st = c.get("/api/status").json()
    assert "have_samples" in st and isinstance(st["have_samples"], bool)
    assert c.get("/api/clips").json() == []


def test_missing_clip_404(tmp_path):
    assert _client(tmp_path).get("/api/clip/nope").status_code == 404


def test_ingest_requires_source(tmp_path):
    r = _client(tmp_path).post("/api/ingest", json={"name": "x"})
    assert r.status_code == 400


def test_serves_index_html(tmp_path):
    r = _client(tmp_path).get("/")
    assert r.status_code == 200 and "Lost in a Melody" in r.text


# ── the killable job model ────────────────────────────────────────────────────
def _wait(job: Job, timeout=10):
    end = time.time() + timeout
    while job.running() and time.time() < end:
        time.sleep(0.02)


def test_job_runs_and_captures_log():
    job = Job()
    job.start("t", "c", [sys.executable, "-c", "print('hello'); print('world')"])
    _wait(job)
    snap = job.snapshot()
    assert snap["state"] == "done"
    assert snap["log"] == ["hello", "world"]


def test_job_nonzero_is_error():
    job = Job()
    job.start("t", "c", [sys.executable, "-c", "import sys; sys.exit(3)"])
    _wait(job)
    assert job.snapshot()["state"] == "error"


def test_job_kill():
    job = Job()
    job.start("t", "c", [sys.executable, "-c", "import time; time.sleep(30)"])
    time.sleep(0.3)                       # let it actually start
    assert job.kill() is True
    _wait(job)
    snap = job.snapshot()
    assert snap["state"] == "error"
    assert "KILLED by user" in snap["log"]


def test_second_job_rejected_while_running():
    job = Job()
    job.start("t", "c", [sys.executable, "-c", "import time; time.sleep(2)"])
    time.sleep(0.2)
    try:
        job.start("t", "c", [sys.executable, "-c", "print(1)"])
        assert False, "expected RuntimeError"
    except RuntimeError:
        pass
    finally:
        job.kill()
