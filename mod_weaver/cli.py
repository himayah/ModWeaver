"""コマンドライン入口（DESIGN.md §8）。

終了コード: 0=成功 / 2=引数エラー・未登録 genre・ジャンルが対応しないテンポ / 3=生成・検査エラー / 4=I/O エラー /
5=外部ツール（mp3 出力の ffmpeg）が無い・機能不足 / 1=想定外例外。
ログは stderr（WARNING 以上）、バナーは stdout。
画面表示（usage・ジャンル一覧・バナー）は既定で日本語、``-e`` / ``--english`` で英語（DESIGN.md §8.5）。
``--json`` はジャンル一覧・生成結果を機械向けの JSON で stdout に出す（GUI などから呼ぶため。DESIGN.md §8.8）。
"""
from __future__ import annotations

import argparse
import json
import logging
import random
import shlex
import re
import shutil
import sys
import traceback
import unicodedata
from pathlib import Path
from typing import Optional, Sequence

from . import __url__, __version__
from .core import formats, render
from .engine import (
    SEED_RANGE, TEMPO_MAX, TEMPO_MIN, VOICE_FORMATS, Result, TempoRequest, channel_choices, generate, get_genre, has_vocal, list_genres,
    supports_channels,
)
from .errors import (
    ChannelCountError, ExternalToolError, LyricsError, ModGenError, OutputError, ProfileNotFoundError, TempoRangeError,
    VoiceNotFoundError, VoiceUnsupportedError,
)
from .framework import registry

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
        "genre": "ジャンル id（既定: {default}）。{random} ならランダムに選ぶ（選択肢は下のジャンル一覧）",
        "seed": "再現用の乱数シード（任意の整数。省略時はランダム）",
        "format": "出力形式（既定: {default}）。選択肢: {names}",
        "output": "出力先パス（既定: output/<ジャンル>_<シード>.<拡張子>。拡張子は --format に従う）",
        "tempo": "テンポ（4分音符の BPM、{lo}〜{hi}）。80-100 のように範囲を指定するとその中からランダムに決める"
                 "（既定: ジャンルごとに自動）",
        "channels": "チャンネル数。MOD ではジャンルが宣言した数（4/6/8 のうち）から選び、XM・S3M・IT・MP3 では上限として扱う"
                    "（MIDI では指定できない。既定: MOD はジャンルが曲ごとに選び、他の形式は形式の上限）",
        "list_genres": "全ジャンルの id・別名・説明を表示して終了する",
        "english": "使い方・ジャンル一覧・実行結果の表示を英語にする",
        "voice": "歌声を加える。formant（組込みの声）か、modweaver_voice.py で取り込んだ音源の id（歌声パートを持つジャンルだけ。IT・XM・S3M・MP3・MIDI）",
        "lyrics": "歌詞（ひらがな・カタカナ・ローマ字）。文字列、または @ファイル（[区間名] で区切る。書式は DESIGN.md §13.4.1）。--voice が要る",
        "voices_dir": "音源（歌声）の置き場所（既定の探索順は DESIGN.md §13.5.3.1）",
        "list_voices": "取り込み済みの音源を表示して終了する（--json で機械向け）",
        "version": "バージョンと GitHub リポジトリの URL を表示して終了する",
        "output_dir": "--output を省略したときの出力フォルダ（既定: output。無ければ作る）",
        "json": "ジャンル一覧（--list-genres）・生成結果を機械向けの JSON で出す",
        "epilog_head": "ジャンル一覧（{n} 種類）:",
        "epilog_tail": "各ジャンルの説明は --list-genres で表示します",
        "alias": "別名",
        "categories": {"mood": "気分", "genre": "ジャンル", "style": "〜風"},
        "genre_label": "ジャンル",
        "format_label": "出力形式",
        "seed_label": "シード",
        "tempo_label": "テンポ",
        "channels_label": "チャンネル",
        "output_label": "出力ファイル",
        "random": "ランダム",
        "requested": "指定",
        "limit": "上限",
        "success": "生成に成功しました。同じ曲を再現するには次を実行してください:",
    },
    "en": {
        "description": "ModWeaver: Procedural tracker music generator (MOD/XM/S3M/IT/MIDI/MP3)",
        "usage_prefix": "usage: ",
        "options_title": "options",
        "help": "show this help message and exit",
        "genre": "genre id (default: {default}), or {random} to pick one at random (see the genre list below)",
        "seed": "random seed (any integer) for reproducibility (default: random)",
        "format": "output format (default: {default}). choices: {names}",
        "output": "output file path (default: output/<genre>_<seed>.<ext>, extension follows --format)",
        "tempo": "tempo in quarter-note BPM ({lo}-{hi}); a range such as 80-100 picks a random BPM within it "
                 "(default: chosen by the genre)",
        "channels": "number of channels. For MOD it must be one of the counts the genre declares (4/6/8); for XM, S3M, IT "
                    "and MP3 it is an upper limit (not allowed for MIDI). Default: MOD is chosen by the genre for each "
                    "song, other formats use the format's maximum",
        "list_genres": "print all genre ids, aliases and descriptions, then exit",
        "english": "show the usage, genre list and results in English",
        "voice": "add a sung part: formant (built-in voice) or the id of a voice bank imported with modweaver_voice.py (genres with a vocal part; IT, XM, S3M, MP3, MIDI)",
        "lyrics": "lyrics (hiragana, katakana or romaji): a string, or @FILE with [section] blocks (format: DESIGN.md 13.4.1). Needs --voice",
        "voices_dir": "where voice banks are searched (default search order: DESIGN.md 13.5.3.1)",
        "list_voices": "list the imported voice banks and exit (--json for machine-readable output)",
        "version": "print the version and the GitHub repository URL, then exit",
        "output_dir": "folder for the output file when --output is omitted (default: output; created if missing)",
        "json": "print the genre list (--list-genres) or the generation result as machine-readable JSON",
        "epilog_head": "genres ({n}):",
        "epilog_tail": "use --list-genres to see what each genre sounds like",
        "alias": "alias",
        "categories": {"mood": "Mood", "genre": "Genre", "style": "Style"},
        "genre_label": "Genre",
        "format_label": "Format",
        "seed_label": "Seed",
        "tempo_label": "Tempo",
        "channels_label": "Channels",
        "output_label": "Output File",
        "random": "random",
        "requested": "requested",
        "limit": "limit",
        "success": "Success! To reproduce this exact song, run:",
    },
}


def default_output_path(genre_id: str, seed: int, fmt: str = formats.DEFAULT_FORMAT,
                        directory: Optional[Path] = None) -> Path:
    """``--output`` 省略時の既定出力先: ``output/<genre>_<seed><ext>``（カレントディレクトリの ``output`` にまとめる）。
    ``directory``（``--output-dir``）を渡せば ``output`` の代わりにそのフォルダ。

    拡張子は出力形式の ``OutputFormat.extension``（``mod``→``.mod``、``midi``→``.mid``）。中身の形式と
    拡張子を一致させないと、プレイヤー側がマジックバイトと拡張子の不一致で読み込みに失敗する。"""
    folder = OUTPUT_DIR if directory is None else Path(directory)
    return folder / f"{genre_id}_{seed}{formats.get_format(fmt).extension}"


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


def _by_category() -> list[tuple[str, list]]:
    """登録ジャンルを区分（registry.CATEGORIES の順）ごとに id 順でまとめる。空の区分は除く。"""
    groups = {c: [] for c in registry.CATEGORIES}
    for p in list_genres():
        groups[p.category].append(p)
    return [(c, ps) for c, ps in groups.items() if ps]


def genre_listing(lang: str = "ja") -> str:
    """``--list-genres``: 区分ごとに全ジャンルの id・別名・1行説明を整形する（DESIGN.md §8.1）。"""
    m = MESSAGES[lang]
    lines = []
    for cat, ps in _by_category():
        if lines:
            lines.append("")
        lines.append(f"{m['categories'][cat]} ({cat}):")
        for p in ps:
            alias = f" ({m['alias']}: {', '.join(p.aliases)})" if p.aliases else ""
            lines.append(f"  {p.id}{alias}\n      {p.description_en if lang == 'en' else p.description}")
    return "\n".join(lines)


def ffmpeg_status() -> dict:
    """mp3 出力に使う ffmpeg の状態（``--list-genres --json`` 用）。検査は ``render.check_ffmpeg`` と同じ。"""
    try:
        return {"available": True, "ffmpeg": render.check_ffmpeg(), "error": None}
    except ExternalToolError as e:
        return {"available": False, "ffmpeg": None, "error": str(e)}


def _format_channels(fmt) -> Optional[dict]:
    """形式ごとの ``--channels`` の意味（GUI が選択肢を作る）。``{"choices": [4, 6, 8]}``（ジャンルが宣言した数から選ぶ）・
    ``{"max": 16}``（上限）・``None``（指定不可）。"""
    if fmt.channels == "choices":
        return {"choices": sorted({n for g in list_genres() for n in channel_choices(g)})}
    if fmt.channels == "max":
        return {"max": formats.channel_limit(fmt.name)}
    return None


def catalog() -> dict:
    """``--list-genres --json``: GUI などが起動時に読む、CLI で選べるもの一式（DESIGN.md §8.8）。

    ジャンルの説明・区分名は日英の両方を入れる（呼ぶ側が表示言語を切り替えても再取得しなくて済むように）。"""
    fmts = formats.get_formats()
    return {
        "version": __version__,
        "url": __url__,
        "default_genre": DEFAULT_GENRE,
        "random_genre": list(RANDOM_GENRE),
        "default_format": formats.DEFAULT_FORMAT,
        "formats": [{"name": f.name, "extension": f.extension, "description": f.description,
                     "channels": _format_channels(f)} for f in fmts.values()],
        "tempo": {"min": TEMPO_MIN, "max": TEMPO_MAX},
        "seed_range": list(SEED_RANGE),
        "categories": [{"id": c, "ja": MESSAGES["ja"]["categories"][c], "en": MESSAGES["en"]["categories"][c]}
                       for c, _ in _by_category()],
        "genres": [
            {
                "id": p.id,
                "display_name": p.display_name,
                "category": p.category,
                "aliases": list(p.aliases),
                "description": p.description,
                "description_en": p.description_en,
                "tempo_range": list(p.tempo_range),
                "tempo_choices": sorted(p.tempo_choices),
                "mod_channels": list(channel_choices(p)),
                "channel_cap": p.channel_cap,
                "vocal": has_vocal(p),
            }
            for _, ps in _by_category() for p in ps
        ],
        "mp3": ffmpeg_status(),
        "voice_formats": list(VOICE_FORMATS),
    }


def result_json(genre, result: Result, repro: str, random_genre: bool) -> dict:
    """``--json`` の生成結果。バナーと同じ内容を機械向けに（DESIGN.md §8.8）。"""
    plan = result.plan
    requested = result.tempo_request
    return {
        "genre": genre.id,
        "display_name": genre.display_name,
        "random_genre": random_genre,
        "format": result.fmt,
        "seed": result.seed,
        "bpm": plan.bpm,
        "tempo_request": None if requested is None else str(requested),
        "channels": result.channels,
        "channel_budget": result.channel_budget,
        "sample_bits": result.sample_bits,
        "channels_request": result.channels_request,
        "summary": list(plan.summary),
        "path": str(Path(result.path).resolve()) if result.path is not None else None,
        "repro": f"{repro} --seed {result.seed}",
        "voice": None if result.voice is None else {
            "id": result.voice.id, "fingerprint": result.voice.fingerprint[:8], "credit": result.voice.credit,
            "terms_url": result.voice.terms_url, "terms_checked": result.voice.terms_checked,
            "credits_path": str(Path(result.credits_path).resolve()) if result.credits_path else None},
        "lyrics": result.lyrics,
    }


def print_json(data: dict) -> None:
    # ASCII だけで出す（Windows でパイプの文字コードが cp932 になっても化けない・落ちない）
    print(json.dumps(data, ensure_ascii=True, indent=1))


def genre_ids_by_category(lang: str = "ja", width: int = 78) -> str:
    """``--help`` 末尾用: 区分ごとの id だけの一覧（説明は ``--list-genres``）。表示幅で折り返す。"""
    m = MESSAGES[lang]
    lines = []
    for cat, ps in _by_category():
        label = f"  {m['categories'][cat]}: "
        indent = " " * _cols(label)
        body = _wrap(", ".join(p.id for p in ps), max(20, width - _cols(label)))
        lines.append(label + body[0])
        lines.extend(indent + b for b in body[1:])
    return "\n".join(lines)


def pick_random_genre(tempo: Optional[TempoRequest] = None, channels: Optional[int] = None,
                      fmt: str = formats.DEFAULT_FORMAT, seed: int = 0) -> str:
    """``--genre random`` の選択（DESIGN.md §8.3）。候補は正規 id のみ（別名で確率が偏らないように）。

    ``--tempo`` があれば ``tempo_range`` が要求と重なるジャンルだけ、``--channels`` があればその数でこの形式を作れる
    ジャンル（MOD は宣言した数、他の形式は上限の中に収まるもの）だけを候補にする。乱数は seed と独立。"""
    candidates = [
        p.id for p in list_genres()
        if tempo is None or max(tempo.lo, p.tempo_range[0]) <= min(tempo.hi, p.tempo_range[1])
    ]
    if not candidates:
        raise TempoRangeError(f"no genre supports tempo {tempo}")
    if channels is not None:
        candidates = [g for g in candidates if supports_channels(get_genre(g), fmt, channels, seed)]
        if not candidates:
            raise ChannelCountError(f"no genre supports {channels} channels" + (f" at tempo {tempo}" if tempo else ""))
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
        if line and _cols(line + tok) > width:
            if tok not in _NO_LINE_START:
                lines.append(line.rstrip())
                line = ""
            elif _cols(line) > width:                       # 句読点・閉じ括弧が続いて溢れる: 直前の1文字ごと次の行へ送る
                j = len(line)
                while j > 0 and line[j - 1] in _NO_LINE_START:
                    j -= 1
                if j > 0 and "!" <= line[j - 1] <= "~":        # 英数字の語は分割しない（語ごと送る）
                    while j > 0 and "!" <= line[j - 1] <= "~":
                        j -= 1
                else:
                    j -= 1
                if j > 0 and (_cols(line[j]) == 2 or "!" <= line[j] <= "~"):
                    lines.append(line[:j].rstrip())
                    line = line[j:]
        if line or not tok.isspace():
            line += tok
    if line:
        lines.append(line.rstrip())
    return lines


def build_parser(prog: Optional[str] = None, lang: str = "ja") -> argparse.ArgumentParser:
    m = MESSAGES[lang]
    names = formats.format_names()
    width = max(40, shutil.get_terminal_size().columns - 2)
    parser = argparse.ArgumentParser(
        prog=prog,
        description=m["description"],
        epilog=(m["epilog_head"].format(n=len(list_genres())) + "\n"
                + genre_ids_by_category(lang, width) + "\n\n" + m["epilog_tail"]),
        formatter_class=_formatter_class(lang),
        add_help=False,
    )
    opts = parser.add_argument_group(m["options_title"])   # argparse 既定の見出し（英語）の代わり
    opts.add_argument("--help", "-h", action="help", help=m["help"])
    opts.add_argument("--genre", "-g", default=DEFAULT_GENRE,
                      help=m["genre"].format(default=DEFAULT_GENRE, random="/".join(RANDOM_GENRE)))
    opts.add_argument("--seed", "-s", type=int, default=None, help=m["seed"])
    opts.add_argument("--format", "-f", choices=names, default=None,
                      help=m["format"].format(default=formats.DEFAULT_FORMAT, names=", ".join(names)))
    out = opts.add_mutually_exclusive_group()
    out.add_argument("--output", "-o", type=str, default=None, help=m["output"])
    out.add_argument("--output-dir", type=str, default=None, metavar="DIR", help=m["output_dir"])
    opts.add_argument("--tempo", "-t", type=_tempo_arg, default=None, metavar="BPM|MIN-MAX",
                      help=m["tempo"].format(lo=TEMPO_MIN, hi=TEMPO_MAX))
    opts.add_argument("--channels", "-c", type=int, default=None, metavar="N", help=m["channels"])
    opts.add_argument("--voice", type=str, default=None, metavar="ID", help=m["voice"])
    opts.add_argument("--lyrics", type=str, default=None, metavar="TEXT|@FILE", help=m["lyrics"])
    opts.add_argument("--voices-dir", type=str, default=None, metavar="DIR", help=m["voices_dir"])
    opts.add_argument("--list-voices", action="store_true", help=m["list_voices"])
    opts.add_argument("--list-genres", action="store_true", help=m["list_genres"])
    opts.add_argument("--json", action="store_true", help=m["json"])
    opts.add_argument("--english", "-e", action="store_true", help=m["english"])
    opts.add_argument("--version", "-v", action="version", version=f"ModWeaver {__version__}\n{__url__}",
                      help=m["version"])
    return parser


def _label(text: str, width: int = 12) -> str:
    """バナーの見出しを表示幅（全角=2桁）で ``width`` 桁に揃える。"""
    return text + " " * max(0, width - _cols(text)) + ": "


def print_banner(genre, result: Result, repro: str, random_genre: bool = False, lang: str = "ja") -> None:
    """生成結果の表示。ジャンルの要約行（``plan.summary``。コード進行等の音楽用語）は言語によらずそのまま出す。"""
    m = MESSAGES[lang]
    print(LINE)
    print(f"  ModWeaver: {genre.display_name}")
    print(LINE)
    print(_label(m["genre_label"]) + genre.id + (f" ({m['random']})" if random_genre else ""))
    print(_label(m["format_label"]) + result.fmt)
    print(_label(m["seed_label"]) + str(result.seed))
    requested = result.tempo_request
    note = f" ({m['requested']} {requested})" if requested is not None and requested.lo != requested.hi else ""
    print(_label(m["tempo_label"]) + f"BPM {result.plan.bpm}{note}")
    limit = f" ({m['limit']} {result.channel_budget})" if result.fmt not in ("mod", "midi") else ""
    print(_label(m["channels_label"]) + str(result.channels) + limit
          + (f" ({m['requested']})" if result.channels_request and not limit else ""))
    for line in result.plan.summary:
        print(line)
    if result.voice is not None:
        v = result.voice
        extra = "" if v.id == "formant" else f"  [{v.fingerprint[:8]}] {v.credit}" + \
            ("" if v.terms_checked else f"  (check the terms: {v.terms_url or 'no URL recorded'})")
        print(_label("Voice" if lang == "en" else "歌声") + v.id + extra)
    print(THIN)
    print(_label(m["output_label"]) + str(result.path))
    print(m["success"])
    print(f"  {repro} --seed {result.seed}")
    print(LINE)


def _list_voices(voices_dir: Optional[str], as_json: bool) -> int:
    """``--list-voices``: 取り込み済みの音源（id・言語・音節数・クレジット・規約確認の状態）。"""
    from .voice.bank import cache, discover

    rows = [{"id": "formant", "lang": "ja", "syllables": None, "credit": "", "terms_checked": True,
             "builtin": True}]
    for vid, folder in discover.installed(discover.search_dirs(voices_dir)).items():
        info = cache.load_info(folder)
        rows.append({"id": vid, "lang": info.lang, "syllables": len(info.syllables), "credit": info.credit,
                     "terms_checked": info.terms_checked, "builtin": False, "path": str(folder)})
    if as_json:
        print_json(rows)
    else:
        for r in rows:
            flag = "" if r["terms_checked"] else "  [terms not checked]"
            n = "built-in" if r["builtin"] else f"{r['syllables']} syllables"
            print(f"{r['id']}  lang={r['lang']}  {n}  {r['credit']}{flag}")
    return 0


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
        if args.json:
            print_json(catalog())
        else:
            print(genre_listing(lang))
        return 0

    if args.list_voices:
        return _list_voices(args.voices_dir, args.json)

    random_genre = args.genre in RANDOM_GENRE
    try:
        seed = args.seed if args.seed is not None else random.randint(*SEED_RANGE)
        fmt = args.format or formats.DEFAULT_FORMAT
        genre = get_genre(pick_random_genre(args.tempo, args.channels, fmt, seed) if random_genre else args.genre)
        if args.output:
            out = args.output
        else:
            out = default_output_path(genre.id, seed, fmt, args.output_dir)
            try:
                out.parent.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                raise OutputError(f"cannot create directory {out.parent}: {e}") from e
        result = generate(genre, seed, out, tempo=args.tempo, fmt=fmt, channels=args.channels, voice=args.voice,
                          voices_dir=args.voices_dir, lyrics=args.lyrics)
    except (ProfileNotFoundError, TempoRangeError, ChannelCountError, VoiceNotFoundError, VoiceUnsupportedError,
            LyricsError) as e:
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
        repro = f"{invocation or 'python -m mod_weaver.cli'} --genre {genre.id}"
    if args.format is not None:
        repro += f" --format {args.format}"
    if args.tempo is not None:
        repro += f" --tempo {result.plan.bpm}"     # 範囲ではなく確定値を出す
    if args.channels is not None:
        repro += f" --channels {args.channels}"   # 指定しなければ seed で同じ編成になる
    if args.voice:
        repro += f" --voice {args.voice}" + (f" --voices-dir {args.voices_dir}" if args.voices_dir else "")
    if args.lyrics:
        repro += f" --lyrics {shlex.quote(args.lyrics)}"
    if args.json:
        print_json(result_json(genre, result, repro, random_genre))
    else:
        print_banner(genre, result, repro, random_genre, lang)
    return 0


if __name__ == "__main__":
    sys.exit(main())
