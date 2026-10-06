"""音源の管理 CLI（``modweaver_voice.py``。DESIGN.md §13.7.2）。標準ライブラリのみ。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from .errors import ModGenError, VoiceBankError
from .voice.bank import audition, cache, discover, importer, synthetic

EXIT_OK, EXIT_ARGS, EXIT_BANK = 0, 2, 3


def _parser(prog: str) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog=prog, description="ModWeaver voice bank (UTAU oto.ini) tool")
    p.add_argument("--voices-dir", help="where installed voices are searched (default: see DESIGN.md 13.5.3.1)")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="read-only inspection of a voice folder")
    c.add_argument("folder", type=Path)
    i = sub.add_parser("import", help="import a voice folder (writes <folder>/.modweaver/)")
    i.add_argument("folder", type=Path)
    i.add_argument("--id")
    i.add_argument("--rate", type=int, default=importer.TARGET_RATE)
    l = sub.add_parser("list", help="list installed voices")
    l.add_argument("--json", action="store_true")
    n = sub.add_parser("info", help="credit, terms memo, fingerprint, home F0")
    n.add_argument("id")
    a = sub.add_parser("audition", help="play a voice alone as a small IT song")
    a.add_argument("id")
    a.add_argument("--text", default="あいうえお")
    a.add_argument("--out", type=Path)
    a.add_argument("--no-align", action="store_true", help="disable preroll alignment (to compare)")
    t = sub.add_parser("make-test-bank", help="generate a synthetic test bank (no third-party data)")
    t.add_argument("folder", type=Path)
    t.add_argument("--encoding", default="utf-8", choices=["utf-8", "cp932"])
    t.add_argument("--multipitch", action="store_true", help="three pitch ranges with a prefix.map (multi-pitch bank)")
    return p


def _dirs(args) -> list[Path]:
    return discover.search_dirs(args.voices_dir)


def _cmd_check(args) -> int:
    r = importer.check(args.folder)
    print(f"oto.ini entries: {r.entries}  CV aliases: {len(r.cv)}  style: {r.style}")
    for w in r.missing_wavs:
        print(f"  missing wav: {w}")
    for b in r.bad_lines[:20]:
        print(f"  oto.ini {b}")
    if r.skipped:
        print(f"  skipped: {len(r.skipped)} (e.g. {r.skipped[0][0]!r}: {r.skipped[0][1]})")
    for n in r.notes:
        print(f"  note: {n}")
    return EXIT_OK if r.cv else EXIT_BANK


def _cmd_import(args) -> int:
    done = [0]

    def prog(alias: str) -> None:
        done[0] += 1
        if done[0] % 10 == 0:
            print(f"  ... {done[0]}", file=sys.stderr, flush=True)

    info, report = importer.import_bank(args.folder, id_override=args.id or "", rate=args.rate, progress=prog)
    print(report, end="")
    print(f"fingerprint: {info.fingerprint[:8]}  ->  {args.folder / cache.DIR}")
    return EXIT_OK


def _cmd_list(args) -> int:
    rows = []
    for vid, folder in discover.installed(_dirs(args)).items():
        info = cache.load_info(folder)
        rows.append({"id": vid, "lang": info.lang, "syllables": len(info.syllables), "credit": info.credit,
                     "terms_checked": info.terms_checked, "fingerprint": info.fingerprint[:8], "path": str(folder)})
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
    elif not rows:
        print("no voices installed")
    for r in rows if not args.json else []:
        flag = "" if r["terms_checked"] else "  [terms not checked]"
        print(f"{r['id']}  lang={r['lang']}  {r['syllables']} syllables  {r['fingerprint']}  {r['credit']}{flag}")
    return EXIT_OK


def _cmd_info(args) -> int:
    folder = discover.find(args.id, _dirs(args))
    info = cache.load_info(folder)
    print(f"id: {info.id}\nlang: {info.lang}\nrate: {info.rate} Hz\nfingerprint: {info.fingerprint}")
    print(f"home F0: {info.home_hz and round(info.home_hz, 1)} Hz\ncredit: {info.credit}")
    print(f"terms_url: {info.terms_url}\nterms_checked: {info.terms_checked}\nsyllables: {len(info.syllables)}")
    rep = folder / cache.DIR / "report.txt"
    if rep.is_file():
        print("--- report.txt ---")
        print(rep.read_text(encoding="utf-8"), end="")
    return EXIT_OK


def _cmd_audition(args) -> int:
    folder = discover.find(args.id, _dirs(args))
    data, notes = audition.render(folder, args.text, align=not args.no_align)
    out = args.out or Path("output") / f"audition_{args.id}.it"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    for n in notes:
        print(f"note: {n}")
    print(f"wrote {out} ({len(data)} bytes)")
    return EXIT_OK


def _cmd_make_test_bank(args) -> int:
    aliases = synthetic.make_test_bank(args.folder, encoding=args.encoding,
                                       pitches=synthetic.MULTI_PITCH if args.multipitch else ())
    print(f"wrote synthetic test bank ({len(aliases)} syllables) to {args.folder}")
    print(f"next: python modweaver_voice.py import {args.folder}")
    return EXIT_OK


_COMMANDS = {"check": _cmd_check, "import": _cmd_import, "list": _cmd_list, "info": _cmd_info,
             "audition": _cmd_audition, "make-test-bank": _cmd_make_test_bank}


def main(argv: Optional[list[str]] = None, prog: str = "modweaver_voice.py") -> int:
    args = _parser(prog).parse_args(argv)
    try:
        return _COMMANDS[args.cmd](args)
    except VoiceBankError as e:
        print(f"error: {e}", file=sys.stderr)
        return EXIT_BANK
    except ModGenError as e:
        print(f"error: {e}", file=sys.stderr)
        return EXIT_ARGS
