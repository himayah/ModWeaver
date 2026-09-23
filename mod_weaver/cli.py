"""コマンドライン入口（DESIGN.md §8）。

終了コード: 0=成功 / 2=引数エラー・未登録 genre・ジャンルが対応しないテンポ / 3=生成・検査エラー / 4=I/O エラー /
5=外部ツール（mp3 出力の ffmpeg）が無い・機能不足 / 1=想定外例外。
ログは stderr（WARNING 以上）、バナーは stdout。
画面表示（usage・ジャンル一覧・バナー）は既定で日本語、``-e`` / ``--english`` で英語（DESIGN.md §8.5）。
"""
from __future__ import annotations

import argparse
import logging
import random
import re
import sys
import traceback
import unicodedata
from pathlib import Path
from typing import Optional, Sequence

from . import __url__, __version__, profiles
from .core import formats
from .engine import SEED_RANGE, TEMPO_MAX, TEMPO_MIN, Result, TempoRequest, generate
from .errors import ExternalToolError, ModGenError, OutputError, ProfileNotFoundError, TempoRangeError

DEFAULT_GENRE = "nostalgic"
RANDOM_GENRE = ("random", "r")   # --genre に指定するとジャンルをランダムに選ぶ（registry.RESERVED_NAMES と同じ）
LINE = "=" * 50
THIN = "-" * 50


OUTPUT_DIR = Path("output")

# 画面に出す文言（既定は日本語、-e / --english で英語）。stderr のエラー・警告は対象外（英語のまま）
MESSAGES = {
    "ja": {
        "description": "ModWeaver: トラッカー音楽を手続き的に自動生成します（MOD/XM/S3M/IT/MIDI/MP3）",
        "usage_prefix": "使い方: ",
        "options_title": "オプション",
        "help": "この使い方を表示して終了する",
        "genre": "ジャンル id（既定: {default}）。{random} ならランダムに選ぶ。選択肢: {ids}（下のジャンル一覧を参照）",
        "seed": "再現用の乱数シード（任意の整数。省略時はランダム）",
        "format": "出力形式（既定: {default}）。選択肢: {names}",
        "output": "出力先パス（既定: output/<ジャンル>_<シード>.<拡張子>。拡張子は --format に従う）",
        "tempo": "テンポ（4分音符の BPM、{lo}〜{hi}）。80-100 のように範囲を指定するとその中からランダムに決める"
                 "（既定: ジャンルごとに自動）",
        "list_genres": "全ジャンルの id・別名・説明を表示して終了する",
        "english": "使い方・ジャンル一覧・実行結果の表示を英語にする",
        "version": "バージョンと GitHub リポジトリの URL を表示して終了する",
        "epilog_head": "ジャンル一覧:",
        "epilog_tail": "--list-genres でこの一覧だけを表示して終了します",
        "alias": "別名",
        "genre_label": "ジャンル",
        "format_label": "出力形式",
        "seed_label": "シード",
        "tempo_label": "テンポ",
        "output_label": "出力ファイル",
        "random": "ランダム",
        "requested": "指定",
        "success": "生成に成功しました。同じ曲を再現するには次を実行してください:",
    },
    "en": {
        "description": "ModWeaver: Procedural tracker music generator (MOD/XM/S3M/IT/MIDI/MP3)",
        "usage_prefix": "usage: ",
        "options_title": "options",
        "help": "show this help message and exit",
        "genre": "genre id (default: {default}), or {random} to pick one at random. choices: {ids} "
                 "(see genres below)",
        "seed": "random seed (any integer) for reproducibility (default: random)",
        "format": "output format (default: {default}). choices: {names}",
        "output": "output file path (default: output/<genre>_<seed>.<ext>, extension follows --format)",
        "tempo": "tempo in quarter-note BPM ({lo}-{hi}); a range such as 80-100 picks a random BPM within it "
                 "(default: chosen by the genre)",
        "list_genres": "print all genre ids, aliases and descriptions, then exit",
        "english": "show the usage, genre list and results in English",
        "version": "print the version and the GitHub repository URL, then exit",
        "epilog_head": "genres:",
        "epilog_tail": "use --list-genres to print this list alone and exit",
        "alias": "alias",
        "genre_label": "Genre",
        "format_label": "Format",
        "seed_label": "Seed",
        "tempo_label": "Tempo",
        "output_label": "Output File",
        "random": "random",
        "requested": "requested",
        "success": "Success! To reproduce this exact song, run:",
    },
}


def default_output_path(genre_id: str, seed: int, fmt: str = formats.DEFAULT_FORMAT) -> Path:
    """``--output`` 省略時の既定出力先: ``output/<genre>_<seed><ext>``（カレントディレクトリの ``output`` にまとめる）。

    拡張子は出力形式の ``OutputFormat.extension``（``mod``→``.mod``、``midi``→``.mid``）。中身の形式と
    拡張子を一致させないと、プレイヤー側がマジックバイトと拡張子の不一致で読み込みに失敗する。"""
    return OUTPUT_DIR / f"{genre_id}_{seed}{formats.get_format(fmt).extension}"


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


def genre_listing(lang: str = "ja") -> str:
    """全ジャンルの id・別名・説明を1行ずつ整形する（``--list-genres`` と ``--help`` の両方から使う）。"""
    m = MESSAGES[lang]
    lines = []
    for p in profiles.list_profiles():
        alias = f" ({m['alias']}: {', '.join(p.aliases)})" if p.aliases else ""
        lines.append(f"  {p.id}{alias}\n      {p.description_en if lang == 'en' else p.description}")
    return "\n".join(lines)


def pick_random_genre(tempo: Optional[TempoRequest] = None) -> str:
    """``--genre random`` の選択（DESIGN.md §8.3）。候補は正規 id のみ（別名で確率が偏らないように）。

    ``--tempo`` があれば ``tempo_range`` が要求と重なるジャンルだけを候補にする。乱数は seed と独立。"""
    candidates = [
        p.id for p in profiles.list_profiles()
        if tempo is None or max(tempo.lo, p.tempo_range[0]) <= min(tempo.hi, p.tempo_range[1])
    ]
    if not candidates:
        raise TempoRangeError(f"no genre supports tempo {tempo}")
    return random.choice(candidates)


def _tempo_arg(text: str) -> TempoRequest:
    try:
        return TempoRequest.parse(text)
    except ValueError as e:
        raise argparse.ArgumentTypeError(str(e)) from None


def _formatter_class(lang: str) -> type:
    prefix = MESSAGES[lang]["usage_prefix"]

    class Formatter(argparse.RawDescriptionHelpFormatter):
        def add_usage(self, usage, actions, groups, prefix_=None):  # type: ignore[override]
            super().add_usage(usage, actions, groups, prefix if prefix_ is None else prefix_)

        def _split_lines(self, text, width):  # 標準は len() で折り返すので全角が2桁ぶんはみ出す
            return _wrap(" ".join(text.split()), width)

    return Formatter


def _cols(text: str) -> int:
    """端末での表示幅（全角=2桁）。"""
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in text)


_NO_LINE_START = set("。、，．）」』】")


def _wrap(text: str, width: int) -> list[str]:
    """表示幅で折り返す。英数字の語（``free-jazz,`` 等）は分割せず、日本語は1文字ごとに折り返せる。"""
    lines, line = [], ""
    for tok in re.findall(r"[!-~]+| +|.", text):
        if line and _cols(line + tok) > width and tok not in _NO_LINE_START:   # 句読点・閉じ括弧は行頭に置かない
            lines.append(line.rstrip())
            line = ""
        if line or not tok.isspace():
            line += tok
    if line:
        lines.append(line.rstrip())
    return lines


def build_parser(prog: Optional[str] = None, lang: str = "ja") -> argparse.ArgumentParser:
    m = MESSAGES[lang]
    ids = ", ".join(p.id for p in profiles.list_profiles())
    names = formats.format_names()
    parser = argparse.ArgumentParser(
        prog=prog,
        description=m["description"],
        epilog=m["epilog_head"] + "\n" + genre_listing(lang) + "\n\n" + m["epilog_tail"],
        formatter_class=_formatter_class(lang),
        add_help=False,
    )
    opts = parser.add_argument_group(m["options_title"])   # argparse 既定の見出し（英語）の代わり
    opts.add_argument("--help", "-h", action="help", help=m["help"])
    opts.add_argument("--genre", "-g", default=DEFAULT_GENRE,
                      help=m["genre"].format(default=DEFAULT_GENRE, random="/".join(RANDOM_GENRE), ids=ids))
    opts.add_argument("--seed", "-s", type=int, default=None, help=m["seed"])
    opts.add_argument("--format", "-f", choices=names, default=None,
                      help=m["format"].format(default=formats.DEFAULT_FORMAT, names=", ".join(names)))
    opts.add_argument("--output", "-o", type=str, default=None, help=m["output"])
    opts.add_argument("--tempo", "-t", type=_tempo_arg, default=None, metavar="BPM|MIN-MAX",
                      help=m["tempo"].format(lo=TEMPO_MIN, hi=TEMPO_MAX))
    opts.add_argument("--list-genres", action="store_true", help=m["list_genres"])
    opts.add_argument("--english", "-e", action="store_true", help=m["english"])
    opts.add_argument("--version", "-v", action="version", version=f"ModWeaver {__version__}\n{__url__}",
                      help=m["version"])
    return parser


def _label(text: str, width: int = 12) -> str:
    """バナーの見出しを表示幅（全角=2桁）で ``width`` 桁に揃える。"""
    return text + " " * max(0, width - _cols(text)) + ": "


def print_banner(profile, result: Result, repro: str, random_genre: bool = False, lang: str = "ja") -> None:
    """生成結果の表示。ジャンルの要約行（``plan.summary``。コード進行等の音楽用語）は言語によらずそのまま出す。"""
    m = MESSAGES[lang]
    print(LINE)
    print(f"  ModWeaver: {profile.display_name}")
    print(LINE)
    print(_label(m["genre_label"]) + profile.id + (f" ({m['random']})" if random_genre else ""))
    print(_label(m["format_label"]) + result.fmt)
    print(_label(m["seed_label"]) + str(result.seed))
    requested = result.tempo_request
    note = f" ({m['requested']} {requested})" if requested is not None and requested.lo != requested.hi else ""
    print(_label(m["tempo_label"]) + f"BPM {result.plan.bpm}{note}")
    for line in result.plan.summary:
        print(line)
    print(THIN)
    print(_label(m["output_label"]) + str(result.path))
    print(m["success"])
    print(f"  {repro} --seed {result.seed}")
    print(LINE)


def _is_english_flag(arg: str) -> bool:
    """``-e`` / ``--english``（argparse が受け付ける ``--eng`` 等の省略形を含む）。"""
    return arg == "-e" or (arg.startswith("--e") and "--english".startswith(arg))


def main(
    argv: Optional[Sequence[str]] = None,
    *,
    prog: Optional[str] = None,
    invocation: Optional[str] = None,
    repro: Optional[str] = None,
) -> int:
    """CLI 本体。``invocation`` は再現コマンドの先頭（既定 ``python -m mod_weaver.cli``）。"""
    _configure_logging()
    argv = sys.argv[1:] if argv is None else list(argv)
    # usage の言語は解析前に決める必要があるので -e だけ先に拾う（DESIGN.md §8.2）
    lang = "en" if any(_is_english_flag(a) for a in argv) else "ja"
    parser = build_parser(prog, lang)
    if not [a for a in argv if not _is_english_flag(a)]:
        parser.print_help()           # 引数なし（-e だけも含む）: --help と同じ usage を出して終了（DESIGN.md §8.2）
        return 0
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 2
    if args.english:
        lang = "en"                   # -es 5 のようにまとめて書いた場合

    if args.list_genres:
        print(genre_listing(lang))
        return 0

    random_genre = args.genre in RANDOM_GENRE
    try:
        profile = profiles.get_profile(pick_random_genre(args.tempo) if random_genre else args.genre)
        seed = args.seed if args.seed is not None else random.randint(*SEED_RANGE)
        fmt = args.format or formats.DEFAULT_FORMAT
        if args.output:
            out = args.output
        else:
            out = default_output_path(profile.id, seed, fmt)
            try:
                out.parent.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                raise OutputError(f"cannot create directory {out.parent}: {e}") from e
        result = generate(profile, seed, out, tempo=args.tempo, fmt=fmt)
    except (ProfileNotFoundError, TempoRangeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    except OutputError as e:
        print(f"error: {e}", file=sys.stderr)
        return 4
    except ExternalToolError as e:
        print(f"error: {e}", file=sys.stderr)
        return 5
    except ModGenError as e:
        print(f"error: {e}", file=sys.stderr)
        return 3
    except Exception:  # 想定外。スタックトレースを残す
        traceback.print_exc()
        return 1

    if repro is None:
        repro = f"{invocation or 'python -m mod_weaver.cli'} --genre {profile.id}"
    if args.format is not None:
        repro += f" --format {args.format}"
    if args.tempo is not None:
        repro += f" --tempo {result.plan.bpm}"     # 範囲ではなく確定値を出す
    print_banner(profile, result, repro, random_genre, lang)
    return 0


if __name__ == "__main__":
    sys.exit(main())
