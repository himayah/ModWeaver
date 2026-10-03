"""出力音量の底上げ（DESIGN.md §7.9）。

最大振幅を ``TARGET_PEAK_DB`` に揃える。手段:
- 音量の値（サンプルの既定音量と ``RCell.vol``）を一律に倍にする。上限 64 に当たる曲ではそこまで（音量の比を保つ）。
- S3M のマスター音量・IT の mix volume（既定 48。127/128 まで）。ミキシング後に線形に効くので先に使う。
  XM・MOD にはこれが無いので、音量の値の余裕の範囲でしか持ち上がらない。

どれだけ持ち上げるかは、ジャンル × 形式 × チャンネル数ごとに実プレイヤー（libopenmpt）で測った最悪の最大振幅
（``framework/levels.py``。``tools/calibrate_levels.py`` が作る）から決める。作曲には触れない。
"""
from __future__ import annotations

import dataclasses
import math
from typing import Optional

from .native import RCell, RealizedSong
from .verify import LEFT_CHANNELS, VOLUME_SUM_CHANNELS, VOLUME_SUM_LIMIT

TARGET_PEAK_DB = -2.0
MAX_VOLUME = 64
HEADER_VOLUME = 48
HEADER_VOLUME_MAX = {"s3m": 127, "it": 128}


def level_key(rs: RealizedSong) -> str:
    """測定値の鍵（形式＋チャンネル数。MOD は 4ch と 8ch で音量が大きく違うため）。"""
    return f"{rs.format}{rs.n_channels}"


def volume_room(rs: RealizedSong) -> float:
    """音量の値を何倍まで上げられるか（最大の音量が 64 を超えない）。MOD 4ch は V15（左右の同時合計 ≤120）も守る。"""
    n = rs.n_channels
    sides = rs.format == "mod" and n == VOLUME_SUM_CHANNELS
    vol = [0] * n
    top = side = 0.0
    for p in rs.order:
        g = rs.patterns[p]
        for r in range(g.rows):
            for ch in range(n):
                c = g.get(r, ch)
                if c.note is not None and c.note < 0:
                    vol[ch] = 0
                elif c.note is not None and c.sample:
                    vol[ch] = rs.samples[c.sample - 1].volume if c.vol is None else c.vol
                elif c.vol is not None:
                    vol[ch] = c.vol
                top = max(top, vol[ch])
            if sides:
                left = sum(v for ch, v in enumerate(vol) if ch % 4 in LEFT_CHANNELS)
                side = max(side, left, sum(vol) - left)
    room = MAX_VOLUME / top if top else 1.0
    return min(room, VOLUME_SUM_LIMIT / side) if side else room


def plan(rs: RealizedSong, peak_db: Optional[float]) -> tuple[float, int]:
    """(音量の値に掛ける倍率, マスター音量)。測定値が無い（None）か、すでに目標以上なら持ち上げない。"""
    if peak_db is None:
        return 1.0, HEADER_VOLUME
    want = 10 ** ((TARGET_PEAK_DB - peak_db) / 20)
    if want <= 1.0:
        return 1.0, HEADER_VOLUME
    room = volume_room(rs)
    top = HEADER_VOLUME_MAX.get(rs.format)
    if top is None:
        return min(room, want), HEADER_VOLUME
    header = min(top, math.floor(HEADER_VOLUME * want))
    return (min(room, want * HEADER_VOLUME / header) if header == top else 1.0), header


def apply(rs: RealizedSong, gain: float, header: int) -> RealizedSong:
    def scale(v: int) -> int:
        return min(MAX_VOLUME, math.floor(v * gain + 1e-9))

    if gain > 1.0:
        samples = [dataclasses.replace(s, volume=scale(s.volume)) for s in rs.samples]
        patterns = [g.mapped(lambda c: c if c.vol is None else dataclasses.replace(c, vol=scale(c.vol)))
                    for g in rs.patterns]
    else:
        samples, patterns = rs.samples, rs.patterns
    return dataclasses.replace(rs, samples=samples, patterns=patterns, mix_volume=header)


def lift(rs: RealizedSong, peaks_db: Optional[dict]) -> RealizedSong:
    """``peaks_db``: そのジャンルの ``{level_key: 最悪の最大振幅(dBFS)}``。"""
    peaks_db = peaks_db or {}
    peak = peaks_db.get(level_key(rs))
    if peak is None:     # 測っていないチャンネル数（seed で編成が変わる形式）は、同じ形式の最悪値で代用する
        same = [v for k, v in peaks_db.items() if k.rstrip("0123456789") == rs.format]
        peak = max(same) if same else None
    return apply(rs, *plan(rs, peak))
