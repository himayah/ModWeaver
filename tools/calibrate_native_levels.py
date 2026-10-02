"""新しい枠組み（framework/）のジャンルの実プレイヤーでの最大振幅を測り、mod_weaver/framework/levels.py を作る。

各ジャンルを複数の seed と予算（MOD は宣言された全予算、他形式は既定の予算と ``min(mod_channels)``）で、音量の底上げなしで
作り、ffmpeg 内蔵の libopenmpt で再生して、形式＋チャンネル数ごとの最大振幅の最悪値を記録する。ffmpeg（libopenmpt 入り）が要る。

    python tools/calibrate_native_levels.py            # 全ジャンル
"""
from __future__ import annotations

import array
import math
import pprint
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "framework" / "realize" / "genres"))

from mod_weaver.core import native, native_level  # noqa: E402
from mod_weaver.framework.compose import compose, resolve_plan  # noqa: E402
from mod_weaver.framework.realize.tracker import realize  # noqa: E402
from mod_weaver.framework.target import resolve  # noqa: E402
from tests.realplayer import ffmpeg_with_openmpt  # noqa: E402

SEEDS = range(1, 9)
OUT = ROOT / "mod_weaver" / "framework" / "levels.py"
HEADER = (ROOT / "mod_weaver" / "framework" / "levels.py").read_text(encoding="utf-8").split("PEAK_DB")[0]


def genres() -> dict:
    from march import MarchToy
    from pop import PopToy
    from racing_breaks import RacingBreaksToy
    return {g.id: g for g in (PopToy(), RacingBreaksToy(), MarchToy())}


def peak_db(exe: str, data: bytes, ext: str) -> float:
    with tempfile.TemporaryDirectory() as d:
        src = Path(d) / ("song" + ext)
        src.write_bytes(data)
        out = subprocess.run([exe, "-hide_banner", "-nostdin", "-loglevel", "error", "-f", "libopenmpt", "-i", str(src),
                              "-ac", "2", "-f", "f32le", "-"], capture_output=True, check=True).stdout
    a = array.array("f")
    a.frombytes(out[: len(out) // 4 * 4])
    return 20 * math.log10(max(max(a), -min(a)))


def measure(exe, genre, fmt, channels, seed):
    plan = resolve_plan(genre, seed=seed)
    score = compose(genre, plan, seed=seed, features=frozenset())
    rs = realize(genre, score, plan, resolve(fmt, channels, genre, seed=seed), level=False)
    return native_level.level_key(rs), peak_db(exe, native.serialize(rs), "." + fmt)


def main() -> None:
    exe = ffmpeg_with_openmpt()
    if not exe:
        sys.exit("ffmpeg with libopenmpt is required")
    jobs = []
    for gid, g in genres().items():
        for ch in sorted(g.mod_channels):
            jobs += [(gid, g, "mod", ch, s) for s in SEEDS]
        for fmt in ("s3m", "xm", "it"):
            for ch in (None, min(g.mod_channels)):
                jobs += [(gid, g, fmt, ch, s) for s in SEEDS]
    table: dict[str, dict[str, float]] = {}
    with ThreadPoolExecutor(4) as ex:
        for (gid, *_), (key, db) in zip(jobs, ex.map(lambda j: measure(exe, *j[1:]), jobs)):
            cur = table.setdefault(gid, {})
            cur[key] = round(max(cur.get(key, -99.0), db), 1)
    OUT.write_text(HEADER + "PEAK_DB: dict[str, dict[str, float]] = " + pprint.pformat(table, sort_dicts=True) + "\n",
                   encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
