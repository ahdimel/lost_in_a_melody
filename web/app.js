/* Lost in a Melody — Phase 2 browser player.
 *
 * Talks to the local FastAPI backend (server.py). Handles ingest → trim → process
 * (with status text + KILL), then the Synthesia-style falling-note player over a
 * full 88-key keyboard, with the two toggles (Melody/Full, Original/Simplified).
 *
 * Everything is local: original audio is the backend clip.wav; "simplified" audio is
 * synthesized in the browser with Tone.js (Salamander Sampler if the samples were
 * fetched, else a plain synth) so audio and animation share one clock. */
"use strict";

const $ = (id) => document.getElementById(id);
const api = (p, opts) => fetch(p, opts).then(async (r) => {
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
  return r.json();
});

// ── 88-key geometry (A0=21 … C8=108) ─────────────────────────────────────────
const MIN = 21, MAX = 108;
const isBlack = (m) => [1, 3, 6, 8, 10].includes(((m % 12) + 12) % 12);
const clamp88 = (m) => { while (m < MIN) m += 12; while (m > MAX) m -= 12; return m; };
// One color per pitch class, repeated across octaves.
const pcColor = (m, light) => `hsl(${(((m % 12) + 12) % 12) * 30}, 68%, ${light || 55}%)`;

function buildKeys(width) {
  const whites = [];
  for (let m = MIN; m <= MAX; m++) if (!isBlack(m)) whites.push(m);
  const ww = width / whites.length;
  const keys = {};
  whites.forEach((m, i) => { keys[m] = { x: i * ww, w: ww, black: false }; });
  for (let m = MIN; m <= MAX; m++) {
    if (!isBlack(m)) continue;
    const left = keys[m - 1];              // left neighbor of a black key is always white
    const bw = ww * 0.62;
    keys[m] = { x: left.x + ww - bw / 2, w: bw, black: true };
  }
  return { keys, ww };
}

// ── app state ────────────────────────────────────────────────────────────────
const state = {
  clipId: null,
  data: null,              // /api/clip payload
  flavor: "melody",        // melody | poly
  audioMode: "original",   // original | simplified
  notes: [],               // [{startSec,durSec,pitch,name}] for current flavor
  duration: 0,
  playing: false,
  playhead: 0,
  prevHead: 0,
  lastFrame: 0,
  haveSamples: false,
};

let instrument = null;     // Tone.js Sampler or Synth
let toneReady = false;

// ── ingest ───────────────────────────────────────────────────────────────────
async function ingest(kind) {
  const name = $("name").value.trim();
  if (!name) return setIngest("enter a name first", "error");
  const url = $("url").value.trim();
  const path = $("path").value.trim();
  const body = kind === "url" ? { name, url } : { name, path };
  if (kind === "url" && !url) return setIngest("enter a URL", "error");
  if (kind === "file" && !path) return setIngest("enter a local file path", "error");
  setIngest("fetching…");
  try {
    const res = await api("/api/ingest", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    setIngest(`ingested "${res.id}" (${res.duration.toFixed(1)}s)`, "ok");
    openTrim(res.id, res.duration);
    await refreshLibrary();
  } catch (e) { setIngest(e.message, "error"); }
}
const setIngest = (msg, cls) => { const s = $("ingestStatus"); s.textContent = msg; s.className = "status " + (cls || ""); };

// ── trim ─────────────────────────────────────────────────────────────────────
let trimState = { id: null, dur: 0 };
function openTrim(id, dur) {
  trimState = { id, dur };
  $("trim").classList.remove("hidden");
  $("process").classList.remove("hidden");
  $("sourceAudio").src = `/api/clip/${id}/source`;
  const ts = $("trimStart"), te = $("trimEnd");
  ts.max = te.max = dur; ts.value = 0; te.value = dur;
  updateTrimLabel();
}
function updateTrimLabel() {
  const ts = $("trimStart"), te = $("trimEnd");
  if (+ts.value > +te.value) { const t = ts.value; ts.value = te.value; te.value = t; }
  $("trimLabel").textContent = `${(+ts.value).toFixed(1)} – ${(+te.value).toFixed(1)} s`;
}

// ── process (with polling + KILL) ─────────────────────────────────────────────
let pollTimer = null;
async function startProcess() {
  if (!trimState.id) return;
  const body = {
    id: trimState.id,
    start: +$("trimStart").value,
    end: +$("trimEnd").value,
    stem: $("stem").value || null,
  };
  $("processBtn").disabled = true;
  $("jobLog").textContent = "starting…";
  try {
    await api("/api/process", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    $("killBtn").classList.remove("hidden");
    pollJob();
  } catch (e) {
    $("jobLog").textContent = "error: " + e.message;
    $("processBtn").disabled = false;
  }
}
async function pollJob() {
  clearTimeout(pollTimer);
  const job = await api("/api/job");
  $("jobLog").textContent = job.log.join("\n");
  $("jobLog").scrollTop = $("jobLog").scrollHeight;
  if (job.state === "running") { pollTimer = setTimeout(pollJob, 800); return; }
  $("killBtn").classList.add("hidden");
  $("processBtn").disabled = false;
  if (job.state === "done") { await refreshLibrary(); await loadClip(job.id); }
}
async function killJob() {
  await api("/api/kill", { method: "POST" });
  pollJob();
}

// ── library ──────────────────────────────────────────────────────────────────
async function refreshLibrary() {
  const clips = await api("/api/clips");
  const ul = $("clipList");
  ul.innerHTML = "";
  clips.forEach((c) => {
    const li = document.createElement("li");
    if (!c.processed) li.className = "unprocessed";
    li.innerHTML = `<div>${c.id}</div><div class="meta">${c.processed ?
      `${c.stem || "?"} · ${c.bpm || "?"} bpm` : "not processed"}</div>`;
    li.onclick = () => c.processed ? loadClip(c.id) : openTrimFor(c.id);
    ul.appendChild(li);
  });
}
async function openTrimFor(id) {
  const d = await api(`/api/clip/${id}`);
  if (d.has_source) openTrim(id, d.source_duration);
  else setIngest(`"${id}" has no stored source — re-add it to re-trim`, "error");
}

// ── load a processed clip into the player ─────────────────────────────────────
async function loadClip(id) {
  const d = await api(`/api/clip/${id}`);
  if (!d.processed) return;
  state.clipId = id;
  state.data = d;
  $("player").classList.remove("hidden");
  $("playerTitle").textContent = `${d.meta.title} — ${d.meta.stem || "?"} @ ${d.meta.bpm || "?"} bpm`;
  $("clipAudio").src = `/api/clip/${id}/audio`;
  setFlavor(state.flavor);
  resetPlayback();
  $("player").scrollIntoView({ behavior: "smooth" });
}

function flavorNotes(d, flavor) {
  const j = d[flavor];
  if (!j) return [];
  const bpm = j.bpm || d.meta.bpm || 120;
  const spb = 60 / bpm;
  return j.notes.map((n) => ({
    startSec: n.start * spb,
    durSec: Math.max(0.05, n.length * spb),
    pitch: clamp88(n.pitch),
    name: n.name,
  })).sort((a, b) => a.startSec - b.startSec);
}

function setFlavor(flavor) {
  state.flavor = flavor;
  state.notes = flavorNotes(state.data, flavor);
  const noteEnd = state.notes.reduce((m, n) => Math.max(m, n.startSec + n.durSec), 0);
  const audioDur = $("clipAudio").duration || 0;
  state.duration = Math.max(noteEnd, isFinite(audioDur) ? audioDur : 0, 1);
  $("scrubber").max = state.duration;
  document.querySelectorAll("[data-flavor]").forEach((b) =>
    b.classList.toggle("active", b.dataset.flavor === flavor));
}

// ── playback clock ────────────────────────────────────────────────────────────
// Original: the <audio> element is the authority. Simplified: a wall-clock playhead
// advances and we trigger the sampler as notes cross it (one clock w/ the animation).
function play() {
  if (state.playing) return;
  state.playing = true;
  $("playBtn").textContent = "⏸ Pause";
  if (state.audioMode === "original") {
    $("clipAudio").currentTime = state.playhead;
    $("clipAudio").play();
  } else {
    ensureTone();
    state.prevHead = state.playhead;
  }
  state.lastFrame = performance.now();
}
function pause() {
  state.playing = false;
  $("playBtn").textContent = "▶ Play";
  $("clipAudio").pause();
}
function togglePlay() { state.playing ? pause() : play(); }
function resetPlayback() { pause(); seek(0); }
function seek(t) {
  state.playhead = Math.max(0, Math.min(t, state.duration));
  state.prevHead = state.playhead;
  if (state.audioMode === "original") $("clipAudio").currentTime = state.playhead;
  $("scrubber").value = state.playhead;
}

// ── audio: Tone.js instrument (Sampler if samples present, else Synth) ─────────
function ensureTone() {
  if (!toneReady) { Tone.start(); toneReady = true; }
  if (instrument) return;
  if (state.haveSamples) {
    const urls = {};
    // mirror server.py's Salamander subset: A0, then A/C/D#/F# per octave, then C8
    urls["A0"] = "A0.mp3";
    for (let o = 1; o <= 7; o++) for (const p of ["A", "C", "D#", "F#"])
      urls[`${p}${o}`] = `${p.replace("#", "s")}${o}.mp3`;
    urls["C8"] = "C8.mp3";
    instrument = new Tone.Sampler({ urls, baseUrl: "/assets/samples/" }).toDestination();
  } else {
    instrument = new Tone.PolySynth(Tone.Synth).toDestination();
  }
}

// ── the animation / render loop ───────────────────────────────────────────────
const canvas = $("stage");
const ctx = canvas.getContext("2d");
function resizeCanvas() {
  // No-op while the canvas is hidden (clientWidth 0); re-checked every frame so it
  // self-heals the first time the player section becomes visible.
  const dpr = window.devicePixelRatio || 1;
  const w = Math.round(canvas.clientWidth * dpr), h = Math.round(canvas.clientHeight * dpr);
  if (w === 0 || h === 0) return false;
  if (canvas.width !== w || canvas.height !== h) {
    canvas.width = w; canvas.height = h;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  return true;
}
window.addEventListener("resize", resizeCanvas);

const PX_PER_SEC = 150;
const KEYBOARD_H = 110;

function frame(now) {
  requestAnimationFrame(frame);
  // advance the clock
  if (state.playing) {
    if (state.audioMode === "original") {
      const a = $("clipAudio");
      state.playhead = a.currentTime;
      if (a.ended || state.playhead >= state.duration) pause();
    } else {
      const dt = (now - state.lastFrame) / 1000;
      state.playhead += dt;
      triggerCrossed(state.prevHead, state.playhead);
      state.prevHead = state.playhead;
      if (state.playhead >= state.duration) pause();
    }
    $("scrubber").value = state.playhead;
  }
  state.lastFrame = now;
  draw();
}

function triggerCrossed(from, to) {
  if (!instrument) return;
  for (const n of state.notes) {
    if (n.startSec >= from && n.startSec < to) {
      try { instrument.triggerAttackRelease(n.name, n.durSec); } catch (_) {}
    } else if (n.startSec >= to) break;   // notes are sorted
  }
}

function draw() {
  if (!resizeCanvas()) return;            // canvas still hidden / zero-sized
  const W = canvas.clientWidth, H = canvas.clientHeight;
  ctx.clearRect(0, 0, W, H);
  if (!state.data) return;
  const keyboardTop = H - KEYBOARD_H;
  const { keys } = buildKeys(W);
  const head = state.playhead;

  // which pitches are sounding now → light their keys
  const active = new Set();
  for (const n of state.notes)
    if (n.startSec <= head && head <= n.startSec + n.durSec) active.add(n.pitch);

  // falling notes (whites first, then blacks on top so overlaps read correctly)
  const drawNote = (n) => {
    const k = keys[n.pitch]; if (!k) return;
    const bottomY = keyboardTop - (n.startSec - head) * PX_PER_SEC;
    const height = n.durSec * PX_PER_SEC;
    const topY = bottomY - height;
    if (bottomY < 0 || topY > keyboardTop) return;
    const y = Math.max(0, topY), yb = Math.min(keyboardTop, bottomY);
    ctx.fillStyle = pcColor(n.pitch, 56);
    roundRect(k.x + 1, y, k.w - 2, Math.max(2, yb - y), 3);
    ctx.fill();
  };
  state.notes.forEach((n) => { if (!isBlack(n.pitch)) drawNote(n); });
  state.notes.forEach((n) => { if (isBlack(n.pitch)) drawNote(n); });

  drawKeyboard(keys, keyboardTop, active);
}

function drawKeyboard(keys, top, active) {
  const W = canvas.clientWidth;
  // white keys
  for (let m = MIN; m <= MAX; m++) {
    if (isBlack(m)) continue;
    const k = keys[m];
    ctx.fillStyle = active.has(m) ? pcColor(m, 62) : "#f4f5f7";
    ctx.fillRect(k.x, top, k.w, KEYBOARD_H);
    ctx.strokeStyle = "#3a3f4c"; ctx.lineWidth = 1;
    ctx.strokeRect(k.x + 0.5, top + 0.5, k.w - 1, KEYBOARD_H - 1);
  }
  // black keys on top
  for (let m = MIN; m <= MAX; m++) {
    if (!isBlack(m)) continue;
    const k = keys[m];
    ctx.fillStyle = active.has(m) ? pcColor(m, 50) : "#20242e";
    ctx.fillRect(k.x, top, k.w, KEYBOARD_H * 0.62);
  }
  // hit line
  ctx.strokeStyle = "#2d6cdf"; ctx.lineWidth = 2;
  ctx.beginPath(); ctx.moveTo(0, top); ctx.lineTo(W, top); ctx.stroke();
  $("clock").textContent = `${state.playhead.toFixed(1)}s / ${state.duration.toFixed(1)}s`;
}

function roundRect(x, y, w, h, r) {
  r = Math.min(r, w / 2, h / 2);
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

// ── audio-mode switch ──────────────────────────────────────────────────────────
function setAudioMode(mode) {
  const wasPlaying = state.playing;
  pause();
  state.audioMode = mode;
  document.querySelectorAll("[data-audio]").forEach((b) =>
    b.classList.toggle("active", b.dataset.audio === mode));
  $("audioNote").textContent = mode === "simplified" && !state.haveSamples
    ? "simplified: using a basic synth (run `lam fetch-samples` for real piano)" : "";
  if (wasPlaying) play();
}

// ── wire up ─────────────────────────────────────────────────────────────────
function init() {
  $("fetchUrl").onclick = () => ingest("url");
  $("loadFile").onclick = () => ingest("file");
  $("trimStart").oninput = updateTrimLabel;
  $("trimEnd").oninput = updateTrimLabel;
  $("processBtn").onclick = startProcess;
  $("killBtn").onclick = killJob;
  $("playBtn").onclick = togglePlay;
  $("resetBtn").onclick = resetPlayback;
  $("scrubber").oninput = (e) => seek(+e.target.value);
  document.querySelectorAll("[data-flavor]").forEach((b) =>
    b.onclick = () => { const p = state.playing; pause(); setFlavor(b.dataset.flavor); if (p) play(); });
  document.querySelectorAll("[data-audio]").forEach((b) =>
    b.onclick = () => setAudioMode(b.dataset.audio));

  resizeCanvas();
  requestAnimationFrame(frame);
  api("/api/status").then((s) => { state.haveSamples = s.have_samples; });
  refreshLibrary();
}
init();
