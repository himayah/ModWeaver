"""ジャンルごとの実プレイヤーでの最大振幅を測り、mod_weaver/profiles/levels.py を作り直す（DESIGN.md §7.9）。

各ジャンルを複数の seed（と、編成を選ぶジャンルは全編成）で作曲し、MOD/XM/S3M/IT を音量の底上げなしで
ffmpeg 内蔵の libopenmpt で再生して、形式ごとの最大振幅の最悪値を記録する。ffmpeg（libopenmpt 入り）が要る。

    python tools/calibrate_levels.py              # 全ジャンル
    python tools/calibrate_levels.py rock jazz    # 指定したジャンルだけ測り直す（他の値は残す）
"""
from __future__ import annotations

import argparse
import array
import math
import os
import pprint
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mod_weaver import engine, profiles  # noqa: E402
from mod_weaver.core import render  # noqa: E402
from mod_weaver.profiles.levels import PEAK_DB  # noqa: E402

FORMATS = ("mod", "xm", "s3m", "it")
SEEDS = range(1, 13)                 # 既定の編成（seed から選ばれる）
ARRANGEMENT_SEEDS = (101, 102, 103)  # 編成を選ぶジャンルの各編成
OUT = ROOT / "mod_weaver" / "profiles" / "levels.py"

HEADER = '''"""ジャンルごとの実プレイヤーでの最大振幅（dBFS、音量の底上げ前）。core/level.py が使う。

tools/calibrate_levels.py が生成する。手で編集しない（ジャンルの音量・音色を変えたら作り直す）。
"""
'''


def peak_db(exe: str, data: bytes, ext: str) -> float:
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "song" + ext)
        with open(src, "wb") as f:
            f.write(data)
        out = subprocess.run([exe, "-hide_banner", "-nostdin", "-loglevel", "error", "-f", "libopenmpt",
                              "-i", src, "-ac", "2", "-f", "f32le", "-"], capture_output=True, check=True).stdout
    a = array.array("f")
    a.frombytes(out[: len(out) // 4 * 4])
    return 20 * math.log10(max(max(a), -min(a)))


def measure(exe: str, genre: str, seed: int, channels) -> dict[str, float]:
    p = profiles.get_profile(genre)
    song, plan = engine.compose_song(p, seed, channels=channels)
    return {f: peak_db(exe, engine.serialize(p, song, plan, f, raw=True), "." + f) for f in FORMATS}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("genres", nargs="*", help="測り直すジャンル（省略時は全ジャンル）")
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 4)
    args = ap.parse_args()
    exe = render.check_ffmpeg()
    genres = args.genres or [p.id for p in profiles.list_profiles()]
    runs = []
    for g in genres:
        p = profiles.get_profile(g)
        runs += [(g, s, None) for s in SEEDS]
        runs += [(g, s, n) for n in (p.channel_choices or ()) for s in ARRANGEMENT_SEEDS]
    table = {g: dict(v) for g, v in PEAK_DB.items() if g in {p.id for p in profiles.list_profiles()}}
    for g in genres:
        table[g] = {f: -math.inf for f in FORMATS}
    with ThreadPoolExecutor(args.jobs) as ex:
        for (g, _, _), res in zip(runs, ex.map(lambda r: measure(exe, *r), runs)):
            for f, v in res.items():
                table[g][f] = max(table[g][f], v)
    table = {g: {f: math.ceil(v * 10) / 10 for f, v in table[g].items()} for g in sorted(table)}
    OUT.write_text(HEADER + "PEAK_DB: dict[str, dict[str, float]] = " + pprint.pformat(table, width=110) + "\n",
                   encoding="utf-8")
    print(f"wrote {OUT} ({len(genres)} genres measured)")


if __name__ == "__main__":
    main()
