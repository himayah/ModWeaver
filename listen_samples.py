"""DESIGN.md 第11章の「試聴で調整する項目」を確かめるための曲を、項目ごとに3例ずつ作る。

出力先: output/listen/<番号_項目>/<ジャンル>_<シード>.<拡張子>（output/ は .gitignore 済み）。
  14_arrangements だけは <ジャンル>_<シード>_<チャンネル数>ch.<拡張子>（同じ曲を編成ごとに聴き比べる）。
使い方: ``python listen_samples.py``（Windows は listen_samples.bat のダブルクリックでも可）。
  環境変数 FMT : 出力形式（mod / xm / s3m / it / midi / mp3。既定 mod。mp3 は ffmpeg が必要）
シードは 101, 202, 303（同じシードなら何度作っても同じ曲）。16_racing-breaks だけは系統を揃えるため 101, 102, 113。
第11章の表に試聴の項目を足したら、ここ（ITEMS）にも足す。
"""
from __future__ import annotations

import contextlib
import io
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from mod_weaver import cli  # noqa: E402

SEEDS = (101, 202, 303)

# 第３段階の35ジャンル（10_stage3-balance）
STAGE3 = (
    "acoustic-ssw ambient ambient-drone anime-ost bossa-nova calm cinematic city-pop classical cool dark-tense "
    "dreamy edm energetic focus folk hiphop house indie-rock jazz jpop-80s jrock-90s jrpg lofi-chill lofi-hiphop "
    "melancholic neo-soul pop rnb-soul rock synthwave techno trailer uplifting warm"
).split()

# 編成を選ぶジャンルと、その選べるチャンネル数（14_arrangements）
ARRANGEMENTS = {
    "acoustic-ssw": (4, 6), "anime-ost": (4, 6, 8), "bossa-nova": (4, 6), "cinematic": (6, 8),
    "city-pop": (4, 6, 8), "cool": (4, 6, 8), "dark-tense": (4, 6, 8), "dreamy": (4, 6, 8), "edm": (4, 6, 8),
    "energetic": (4, 6, 8), "folk": (4, 6), "hiphop": (4, 6), "house": (4, 6, 8), "indie-rock": (4, 6, 8),
    "jpop-80s": (4, 6, 8), "jrock-90s": (4, 6, 8), "jrpg": (4, 6, 8), "lofi-chill": (4, 6, 8),
    "lofi-hiphop": (4, 6, 8), "neo-soul": (4, 6, 8), "pop": (4, 6, 8), "rnb-soul": (4, 6, 8), "rock": (4, 6, 8),
    "synthwave": (4, 6, 8), "trailer": (6, 8), "uplifting": (4, 6, 8), "warm": (4, 6),
}


def _one(genre: str, seeds=SEEDS) -> list[tuple[str, int, int | None]]:
    return [(genre, s, None) for s in seeds]


# (フォルダ, 見出し, [(ジャンル, シード, チャンネル数 or None)])
ITEMS: list[tuple[str, str, list[tuple[str, int, int | None]]]] = [
    ("01_swing-jazz", "swing-jazz のスウィング比 - 14:10 のハネ具合", _one("swing-jazz")),
    ("02_trap", "trap のロール確率・808 グライド速度 - ハイハットのロールの多さ、808 のグライドの速さ", _one("trap")),
    ("03_future-bass", "future-bass のダッキング - キックに合わせたベースと和音のうねりの深さ・戻り", _one("future-bass")),
    ("04_maqam", "maqam の旋律の跳躍確率 - ウードの旋律の跳躍の多さ", _one("maqam")),
    ("05_minimalism", "minimalism の音型 - 4つの固定音型のずれと戻り", _one("minimalism")),
    ("06_free-jazz", "free-jazz の密度 - ベース・ピアノ・打楽器・サックスの音の密度", _one("free-jazz")),
    ("07_orchestral", "orchestral のボイシング・音量変化 - 6声の重なりと区間ごとの音量の変化", _one("orchestral")),
    ("08_prog-rock", "prog-rock の lead のビブラート - リードギターにビブラートが要るか", _one("prog-rock")),
    ("09_nostalgic", "nostalgic の pad の −17.6 セント - パッドとオルゴールのわずかなうなり", _one("nostalgic")),
    ("10_stage3-balance", "第３段階の35ジャンルの音量・音色の釣り合い - 各ジャンルのパートの音量と音色の釣り合い（ジャンルごとに3例）",
     [x for g in STAGE3 for x in _one(g)]),
    ("11_folk", "folk の前打音の確率 - フィドルの前打音の多さ", _one("folk")),
    ("12_neo-soul", "neo-soul の「よれ」の確率 - スネアとハットの遅れ具合", _one("neo-soul")),
    ("13_jrpg", "jrpg のゼクエンツ - 旋律の2小節目が1音上がる反復と、音域の上端での頭打ち", _one("jrpg")),
    ("14_arrangements", "曲ごとの編成（4ch で省くパート・8ch で足す任意パート） - 同じシードの曲を編成ごとに聴き比べる"
     "（ジャンルごとに3例 × 選べる編成）",
     [(g, s, n) for g, chs in ARRANGEMENTS.items() for s in SEEDS for n in chs]),
    ("15_new-genres", "gamelan・chiptune・industrial の音量・音色 - ガムランの音律と装飾の密度、チップチューンのアルペジオと"
     "ジャンプ音、インダストリアルの歪み（ジャンルごとに3例）",
     [x for g in ("gamelan", "chiptune", "industrial") for x in _one(g)]),
    ("16_racing-breaks", "racing-breaks の3系統のドラム・ベース、低音の量、エレピの揺れ（系統ごとに1例。系統は seed で決まるので、"
     "101＝ドラムンベース・102＝ブレイクビーツ・113＝2ステップ）", _one("racing-breaks", (101, 102, 113))),
]


def songs() -> list[tuple[str, str, int, int | None]]:
    """作る曲の一覧 (フォルダ, ジャンル, シード, チャンネル数 or None)。"""
    return [(folder, g, s, n) for folder, _title, entries in ITEMS for g, s, n in entries]


def main() -> int:
    with contextlib.suppress(AttributeError, ValueError):   # 出力をファイルに向けたときの文字コード対策
        sys.stdout.reconfigure(errors="replace")
    os.chdir(ROOT)
    fmt = os.environ.get("FMT") or "mod"
    ext = cli.formats.get_format(fmt).extension
    total = len(songs())
    ok = ng = 0
    for folder, title, entries in ITEMS:
        print(f"[{folder}] {title}", flush=True)
        out_dir = Path("output") / "listen" / folder
        out_dir.mkdir(parents=True, exist_ok=True)
        for genre, seed, channels in entries:
            name = f"{genre}_{seed}" + (f"_{channels}ch" if channels else "") + ext
            args = ["--genre", genre, "--seed", str(seed), "--format", fmt, "--output", str(out_dir / name)]
            if channels:
                args += ["--channels", str(channels)]
            with contextlib.redirect_stdout(io.StringIO()):        # バナーは出さない（エラーは stderr に出る）
                code = cli.main(args)
            if code == 0:
                ok += 1
            else:
                ng += 1
                print(f"  失敗: {genre} seed {seed}" + (f" {channels}ch" if channels else ""), flush=True)
    print()
    print(f"完了: 成功 {ok} 件、失敗 {ng} 件（全 {total} 件）。出力先: {Path('output') / 'listen'}")
    return 1 if ng else 0


if __name__ == "__main__":
    sys.exit(main())
