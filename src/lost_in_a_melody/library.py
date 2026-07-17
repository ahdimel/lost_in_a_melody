"""The local library: one self-contained folder per clip (D5).

    library/<clip_id>/
      meta.json     (committed) title, source, trim, bpm, key, chosen stem, ...
      clip.wav      (ignored)   trimmed source
      stems/*.wav   (ignored)
      melody.{mid,json}         the play-along line (top-of-poly)
      poly.{mid,json}           full transcription
      notes.txt     (committed) hand-editable play-along line, in beats
      pianoroll.png (ignored)
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict, field
from pathlib import Path


def _slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9._-]+", "-", name.strip().lower()).strip("-._")
    return s or "clip"


@dataclass
class Meta:
    id: str
    source: str
    is_url: bool
    title: str = ""
    trim_start: float | None = None
    trim_end: float | None = None
    bpm: float | None = None
    key: str | None = None
    stem: str | None = None          # chosen tune-carrier stem
    mode: str = "melody"             # which flavor notes.txt reflects
    transpose: int = 0

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2) + "\n"

    @classmethod
    def from_json(cls, text: str) -> "Meta":
        data = json.loads(text)
        return cls(**{k: data.get(k) for k in cls.__dataclass_fields__})


class Clip:
    def __init__(self, root: Path, clip_id: str):
        self.dir = root / clip_id
        self.id = clip_id

    # paths
    @property
    def meta_path(self) -> Path: return self.dir / "meta.json"
    @property
    def clip_wav(self) -> Path: return self.dir / "clip.wav"
    @property
    def stems_dir(self) -> Path: return self.dir / "stems"
    @property
    def notes_txt(self) -> Path: return self.dir / "notes.txt"
    @property
    def pianoroll(self) -> Path: return self.dir / "pianoroll.png"

    def artifact(self, name: str) -> Path:
        return self.dir / name

    def exists(self) -> bool:
        return self.meta_path.exists()

    def load_meta(self) -> Meta:
        return Meta.from_json(self.meta_path.read_text())

    def save_meta(self, meta: Meta) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        self.meta_path.write_text(meta.to_json())


class Library:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def clip(self, clip_id: str) -> Clip:
        return Clip(self.root, _slug(clip_id))

    def register(self, clip_id: str, source: str, *, is_url: bool,
                 title: str = "", trim_start: float | None = None,
                 trim_end: float | None = None, bpm: float | None = None) -> Clip:
        clip = self.clip(clip_id)
        meta = Meta(id=clip.id, source=source, is_url=is_url,
                    title=title or clip.id, trim_start=trim_start,
                    trim_end=trim_end, bpm=bpm)
        clip.save_meta(meta)
        return clip

    def list_clips(self) -> list[str]:
        return sorted(p.name for p in self.root.iterdir()
                      if (p / "meta.json").exists())
