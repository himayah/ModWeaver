"""コマンドライン入口（設計書 §9、§10）。

終了コード: 0=成功 / 2=引数エラー・未登録 genre・ジャンルが対応しないテンポ / 3=生成・検査エラー / 4=I/O エラー / 1=想定外例外。
ログは stderr（WARNING 以上）、バナーは stdout。
"""
from __future__ import annotations

import argparse
import logging
import random
import sys
import traceback
from pathlib import Path
from typing import Optional, Sequence

from . import profiles
from .engine import SEED_RANGE, TEMPO_MAX, TEMPO_MIN, Result, TempoRequest, generate
from .errors import ModGenError, OutputError, ProfileNotFoundError, TempoRangeError

DEFAULT_GENRE = "nostalgic"
LINE = "=" * 50
THIN = "-" * 50


def default_output_path(genre_id: str, seed: int, target_format: str = "mod") -> Path:
    """``--output`` 省略時の既定出力先: ``<genre>/<genre>_<seed>.<ext>``（ジャンルごとにサブディレクトリへ整理）。

    拡張子は ``target_format``（``profile.target_format``、= ``writer.WRITERS`` のキー）をそのまま使う。
    ``"mod"`` なら ``.mod``、``"xm"`` なら ``.xm``。中身のフォーマットと拡張子を一致させないと、
    プレイヤー側がマジックバイトと拡張子の不一致で読み込みに失敗する（例: orchestral は xm 実体なのに
    .mod 拡張子で保存されると再生できない）。"""
    return Path(genre_id) / f"{genre_id}_{seed}.{target_format}"


def _configure_logging() -> None:
    """ハンドラは cli のみが設定する（ライブラリ層は設定しない）。呼び出しごとに付け替える。"""
    log = logging.getLogger("mod_weaver")
    for h in list(log.handlers):
        if getattr(h, "_modgen_cli", False):
            log.removeHandler(h)
    handler = logging.StreamHandler(sys.stderr)
    handler._modgen_cli = True  # type: ignore[attr-defined]
    handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    log.addHandler(handler)
    log.setLevel(logging.WARNING)
    log.propagate = False


def genre_listing() -> str:
    """全ジャンルの id・別名・説明を1行ずつ整形する（``--list-genres`` と ``--help`` の両方から使う）。"""
    lines = []
    for p in profiles.list_profiles():
        alias = f" (alias: {', '.join(p.aliases)})" if p.aliases else ""
        lines.append(f"  {p.id}{alias}\n      {p.description}")
    return "\n".join(lines)


def _tempo_arg(text: str) -> TempoRequest:
    try:
        return TempoRequest.parse(text)
    except ValueError as e:
        raise argparse.ArgumentTypeError(str(e)) from None


def build_parser(prog: Optional[str] = None) -> argparse.ArgumentParser:
    ids = ", ".join(p.id for p in profiles.list_profiles())
    parser = argparse.ArgumentParser(
        prog=prog,
        description="ModWeaver: Procedural ProTracker MOD Generator",
        epilog="genres:\n" + genre_listing() + "\n\nuse --list-genres to print this list alone and exit",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--genre", "-g", default=DEFAULT_GENRE,
                        help=f"genre id (default: {DEFAULT_GENRE}). choices: {ids} (see genres below)")
    parser.add_argument("--seed", "-s", type=int, default=None,
                        help="random seed (any integer) for reproducibility")
    parser.add_argument("--output", "-o", type=str, default=None,
                        help="output file path (default: <genre>/<genre>_<seed>.<mod|xm>, "
                             "extension depends on the genre's target format)")
    parser.add_argument("--tempo", "-t", type=_tempo_arg, default=None, metavar="BPM|MIN-MAX",
                        help=f"tempo in quarter-note BPM ({TEMPO_MIN}-{TEMPO_MAX}); a range such as 80-100 "
                             "picks a random BPM within it (default: chosen by the genre)")
    parser.add_argument("--list-genres", action="store_true",
                        help="print all genre ids, aliases and descriptions, then exit")
    return parser


def print_banner(profile, result: Result, repro: str) -> None:
    print(LINE)
    print(f"  {profile.display_name} MOD Generator")
    print(LINE)
    print(f"Genre       : {profile.id}")
    print(f"Seed        : {result.seed}")
    requested = result.tempo_request
    note = f" (requested {requested})" if requested is not None and requested.lo != requested.hi else ""
    print(f"Tempo       : BPM {result.plan.bpm}{note}")
    for line in result.plan.summary:
        print(line)
    print(THIN)
    print(f"Output File : {result.path}")
    print("Success! To reproduce this exact song, run:")
    print(f"  {repro} --seed {result.seed}")
    print(LINE)


def main(
    argv: Optional[Sequence[str]] = None,
    *,
    prog: Optional[str] = None,
    invocation: Optional[str] = None,
    repro: Optional[str] = None,
) -> int:
    """CLI 本体。``invocation`` は再現コマンドの先頭（既定 ``python -m mod_weaver.cli``）。"""
    _configure_logging()
    try:
        args = build_parser(prog).parse_args(argv)
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 2

    if args.list_genres:
        print(genre_listing())
        return 0

    try:
        profile = profiles.get_profile(args.genre)
        seed = args.seed if args.seed is not None else random.randint(*SEED_RANGE)
        if args.output:
            out = args.output
        else:
            out = default_output_path(profile.id, seed, profile.target_format)
            try:
                out.parent.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                raise OutputError(f"cannot create directory {out.parent}: {e}") from e
        result = generate(profile, seed, out, tempo=args.tempo)
    except (ProfileNotFoundError, TempoRangeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    except OutputError as e:
        print(f"error: {e}", file=sys.stderr)
        return 4
    except ModGenError as e:
        print(f"error: {e}", file=sys.stderr)
        return 3
    except Exception:  # 想定外。スタックトレースを残す
        traceback.print_exc()
        return 1

    if repro is None:
        repro = f"{invocation or 'python -m mod_weaver.cli'} --genre {profile.id}"
    if args.tempo is not None:
        repro += f" --tempo {result.plan.bpm}"     # 範囲ではなく確定値を出す
    print_banner(profile, result, repro)
    return 0


if __name__ == "__main__":
    sys.exit(main())
