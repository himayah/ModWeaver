"""出力音量の底上げ（DESIGN.md §7.9）。

トラッカー形式の最終的な大きさは再生エンジンのミキシングで決まり、ファイル側で持ち上げる手段は
形式ごとに違う:

- 音量の値（サンプル既定音量と ``Cell.vol``）を一律に倍にする。どの形式でも効くが、上限 64 に当たる
  曲では持ち上げられない（音量どうしの比を保つため、最大の音量が 64 になるところまで）。
- S3M のマスター音量・IT の mix volume（どちらも既定 48）。ミキシング後に線形に効き、127/128 まで上げられる。

どれだけ持ち上げてよいかは、ジャンルごとに実プレイヤー（libopenmpt）で測った最大振幅
（``profiles/levels.py``、``tools/calibrate_levels.py`` が作る）から決め、最大振幅が ``TARGET_PEAK_DB``
になるようにする。作曲には一切触れない（同じ seed なら音符は同じで、大きさだけが変わる）。
"""
from __future__ import annotations

import dataclasses
import math
from typing import Callable, Mapping, Optional, Sequence

from .formats import CENTER
from .model import Cell, Song
from .verify import LEFT_CHANNELS, RIGHT_CHANNELS, VOLUME_SUM_CHANNELS, VOLUME_SUM_LIMIT

TARGET_PEAK_DB = -2.0         # 測った最悪の最大振幅をここまで持ち上げる（未測定の seed のための余裕）
MAX_VOLUME = 64
HEADER_VOLUME = 48            # S3M マスター音量・IT mix volume の既定
HEADER_VOLUME_MAX = {"s3m": 127, "it": 128}


@dataclasses.dataclass(frozen=True)
class Level:
    volume_gain: float = 1.0  # 音量の値に掛ける倍率
    header_volume: int = HEADER_VOLUME   # S3M マスター音量／IT mix volume


Sides = Callable[[int, int], tuple[float, float]]   # (チャンネル, サンプル番号) → (左の重み, 右の重み)


def mod_sides(ch: int, sample: int) -> tuple[float, float]:
    """MOD の V15: Amiga の固定配置（1・4ch が左、2・3ch が右）。"""
    return (1.0, 0.0) if ch % 4 in LEFT_CHANNELS else (0.0, 1.0)


def xm_sides(song: Song, channel_pans: Sequence[int]) -> Sides:
    """XM の V15: 実際に書かれるパン（明示パンのあるサンプルはそのパン、他は ``Px`` に丸めたチャンネルパン）。"""
    def sides(ch: int, sample: int) -> tuple[float, float]:
        spec_pan = song.samples[sample - 1].pan
        pan = spec_pan if spec_pan != CENTER else (channel_pans[ch] >> 4) * 17
        return (255 - pan) / 255, pan / 255
    return sides


def volume_room(song: Song, sides: Optional[Sides] = None) -> float:
    """音量の値を何倍まで上げられるか。最大の音量（音量のあるセル、音量なしで鳴るサンプルの既定音量）が
    64 を超えないこと。``sides`` を渡すと、4ch の曲では検査 V15 の左右の同時合計（verify.py）も上限を
    超えないこと。"""
    n = song.patterns[0].channels if song.patterns else 0
    if n != VOLUME_SUM_CHANNELS:
        sides = None
    vol = [0] * n
    weight = [(0.0, 0.0)] * n
    top = side = 0.0
    for p in song.order:
        pat = song.patterns[p]
        for r in range(pat.rows):
            for ch in range(n):
                c = pat.get(r, ch)
                if c.note is not None and c.sample:
                    vol[ch] = song.samples[c.sample - 1].volume if c.vol is None else c.vol
                    if sides:
                        weight[ch] = sides(ch, c.sample)
                elif c.vol is not None:
                    vol[ch] = c.vol
                top = max(top, vol[ch])
            if sides:
                side = max(side, sum(v * w[0] for v, w in zip(vol, weight)),
                           sum(v * w[1] for v, w in zip(vol, weight)))
    room = MAX_VOLUME / top if top else 1.0
    return min(room, VOLUME_SUM_LIMIT / side) if side else room


def plan_level(song: Song, fmt: str, peaks_db: Optional[Mapping[str, float]],
               channel_pans: Sequence[int] = ()) -> Level:
    """``fmt`` で書き出すときの持ち上げ方。``peaks_db`` はそのジャンルの形式別の測定値（無ければ持ち上げない）。
    ``channel_pans`` は XM の V15 の見積もりに使う。

    MIDI は音割れを測れない（鳴らすのは受け手の音源）ので、最大の音量が velocity 127 になるまで持ち上げる。"""
    sides = {"mod": mod_sides, "xm": xm_sides(song, channel_pans)}.get(fmt)
    room = volume_room(song, sides)
    if fmt == "midi":
        return Level(room)
    key = "xm" if fmt == "mp3" else fmt
    if not peaks_db or key not in peaks_db:
        return Level()
    want = 10 ** ((TARGET_PEAK_DB - peaks_db[key]) / 20)
    if want <= 1.0:
        return Level()
    if fmt in HEADER_VOLUME_MAX:           # ミキシング後に効く値を先に使い、足りない分だけ音量の値で
        top = HEADER_VOLUME_MAX[fmt]
        header = min(top, math.floor(HEADER_VOLUME * want))
        return Level(min(room, want * HEADER_VOLUME / header) if header == top else 1.0, header)
    return Level(min(room, want))


def apply_volume_gain(song: Song, gain: float) -> Song:
    """音量の値を ``gain`` 倍にした Song の複製（``gain`` ≤ 1 ならそのまま返す）。"""
    if gain <= 1.0:
        return song

    def scale(v: int) -> int:
        return min(MAX_VOLUME, math.floor(v * gain + 1e-9))

    def cell(c: Cell) -> Cell:
        return c if c.vol is None else dataclasses.replace(c, vol=scale(c.vol))

    return dataclasses.replace(
        song,
        samples=[dataclasses.replace(s, volume=scale(s.volume)) for s in song.samples],
        patterns=[p.mapped(cell) for p in song.patterns],
    )
