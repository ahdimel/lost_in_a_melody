"""`lam` — the headless CLI. A thin layer over `pipeline.py`.

    lam add   <file | --url URL> --name ID [--bpm N] [--start S --end E]
    lam process ID [--stem NAME] [--no-quantize]
    lam stem  ID --set NAME          # override stem, re-transcribe (cached stems)
    lam show  ID                     # print the note list
    lam render ID                    # re-render from an edited notes.txt
    lam list
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import pipeline
from .library import Library


def _lib(args) -> Library:
    return Library(Path(args.library).expanduser())


def cmd_add(args) -> None:
    lib = _lib(args)
    is_url = args.url is not None
    source = args.url if is_url else args.file
    if not source:
        sys.exit("add: provide a FILE or --url URL")
    pipeline.add(lib, args.name, source, is_url=is_url,
                 start=args.start, end=args.end, bpm=args.bpm, title=args.name)


def cmd_process(args) -> None:
    quantize = None if args.no_quantize else pipeline._tempo.DEFAULT_GRID
    pipeline.process(_lib(args), args.id, stem_override=args.stem, quantize=quantize)


def cmd_stem(args) -> None:
    pipeline.set_stem(_lib(args), args.id, args.set)


def cmd_render(args) -> None:
    pipeline.render(_lib(args), args.id)


def cmd_show(args) -> None:
    clip = _lib(args).clip(args.id)
    if not clip.notes_txt.exists():
        sys.exit(f"{clip.id}: nothing to show — run `process` first")
    sys.stdout.write(clip.notes_txt.read_text())


def cmd_list(args) -> None:
    for name in _lib(args).list_clips():
        print(name)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="lam", description="Lost in a Melody")
    p.add_argument("--library", default="library", help="library root (default ./library)")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add", help="register + acquire/trim a clip")
    a.add_argument("file", nargs="?", help="local audio file")
    a.add_argument("--url", help="fetch audio from a URL instead")
    a.add_argument("--name", required=True, help="clip id")
    a.add_argument("--bpm", type=float, help="set BPM (skips auto-detect)")
    a.add_argument("--start", type=float, help="trim start (seconds)")
    a.add_argument("--end", type=float, help="trim end (seconds)")
    a.set_defaults(func=cmd_add)

    pr = sub.add_parser("process", help="separate + pick stem + transcribe + render")
    pr.add_argument("id")
    pr.add_argument("--stem", help="force a stem (else energy auto-suggest)")
    pr.add_argument("--no-quantize", action="store_true", help="keep raw timing")
    pr.set_defaults(func=cmd_process)

    st = sub.add_parser("stem", help="override stem, re-transcribe (cached stems)")
    st.add_argument("id")
    st.add_argument("--set", required=True, help="stem name")
    st.set_defaults(func=cmd_stem)

    rn = sub.add_parser("render", help="re-render from an edited notes.txt")
    rn.add_argument("id")
    rn.set_defaults(func=cmd_render)

    sh = sub.add_parser("show", help="print the note list")
    sh.add_argument("id")
    sh.set_defaults(func=cmd_show)

    ls = sub.add_parser("list", help="list clips")
    ls.set_defaults(func=cmd_list)
    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
