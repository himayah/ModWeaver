"""音高の表現（設計書 §5.1）。

- tracker note index ``t``: 0=C-1 … 35=B-3（Period 表の並び）。Cell に格納する値
- logical note index ``n``: 実際に鳴る音高。``n = t + shift``（shift は SampleSpec）
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Collection, Sequence

from ..errors import PitchRangeError

NOTE_MIN, NOTE_MAX = 0, 35

_PC_NAMES = ("C-", "C#", "D-", "D#", "E-", "F-", "F#", "G-", "G#", "A-", "A#", "B-")

NOTE_NAMES: tuple[str, ...] = tuple(
    f"{_PC_NAMES[i % 12]}{i // 12 + 1}" for i in range(NOTE_MAX + 1)
)

# ProTracker 標準 PAL Period 表（C-1 .. B-3 の 36 音）
PERIODS: tuple[int, ...] = (
    856, 808, 762, 720, 678, 640, 604, 570, 538, 508, 480, 453,
    428, 404, 381, 360, 339, 320, 302, 285, 269, 254, 240, 226,
    214, 202, 190, 180, 170, 160, 151, 143, 135, 127, 120, 113,
)

_NAME_TO_INDEX = {n: i for i, n in enumerate(NOTE_NAMES)}
_PERIOD_TO_INDEX = {p: i for i, p in enumerate(PERIODS)}

_C1_HZ = 65.4064  # logical note 0（C-1）の周波数


def name(t: int) -> str:
    """tracker note index → 音名（0 -> "C-1"）。"""
    if not NOTE_MIN <= t <= NOTE_MAX:
        raise PitchRangeError(f"note index out of range: {t}")
    return NOTE_NAMES[t]


def parse(s: str) -> int:
    """音名 → index（"C#2" -> 13）。不正は PitchRangeError。"""
    try:
        return _NAME_TO_INDEX[s]
    except KeyError:
        raise PitchRangeError(f"invalid note name: {s!r}") from None


def period_to_index(period: int) -> int:
    """Period 値 → tracker note index。表に無ければ PitchRangeError。"""
    try:
        return _PERIOD_TO_INDEX[period]
    except KeyError:
        raise PitchRangeError(f"period not in table: {period}") from None


def hz(n: int) -> float:
    """logical note index の周波数（Hz）。hz(0)=65.4064。"""
    return _C1_HZ * 2.0 ** (n / 12.0)


def note_for_hz(target_hz: float) -> int:
    """``target_hz`` に最も近い logical note（半音・丸め）。``hz()`` の近似逆関数。

    機械的な単位変換のみを行う（美的判断を含まない）。ある音色を「概ね target_hz で鳴らしたい」
    ときの ``shift = note_for_hz(target_hz) - rate_note`` の計算に使う。
    """
    return round(12.0 * math.log2(target_hz / _C1_HZ))


def fold_into_range(n: int, lo: int, hi: int) -> int:
    """オクターブ単位で [lo, hi] へ折り返す（要 hi−lo ≥ 11）。"""
    if hi - lo < 11:
        raise PitchRangeError(f"range too narrow to fold: [{lo}, {hi}]")
    while n < lo:
        n += 12
    while n > hi:
        n -= 12
    return n


def nearest(pool: Sequence[int], target: int) -> int:
    """pool のうち target に最も近い値（同距離は先頭側＝小さい方が先に並ぶ pool を想定）。"""
    if not pool:
        raise PitchRangeError("empty pool")
    return min(pool, key=lambda x: abs(x - target))


def lowest_note_with_pc(pc: int, lo: int, hi: int) -> int:
    """[lo, hi] 内で pitch class=pc の最低音（hi−lo ≥ 11 を要求）。"""
    if hi - lo < 11:
        raise PitchRangeError(f"range too narrow: [{lo}, {hi}]")
    return lo + ((pc - lo) % 12)


def notes_with_pcs(pcs: Collection[int], lo: int, hi: int) -> list[int]:
    """[lo, hi] 内で pc ∈ pcs の全音（昇順）。"""
    wanted = {p % 12 for p in pcs}
    return [n for n in range(lo, hi + 1) if n % 12 in wanted]


@dataclass(frozen=True)
class Scale:
    tonic_pc: int                    # 0..11（C=0）
    intervals: tuple[int, ...]       # 例 phrygian=(0,1,3,5,7,8,10)

    def notes_in(self, lo: int, hi: int) -> list[int]:
        """範囲内の全 logical note（昇順）。"""
        pcs = {(self.tonic_pc + i) % 12 for i in self.intervals}
        return notes_with_pcs(pcs, lo, hi)


MODES: dict[str, tuple[int, ...]] = {
    "ionian": (0, 2, 4, 5, 7, 9, 11),
    "aeolian": (0, 2, 3, 5, 7, 8, 10),
    "phrygian": (0, 1, 3, 5, 7, 8, 10),
    "dim_wh": (0, 2, 3, 5, 6, 8, 9, 11),
}

CHORD_QUALITIES: dict[str, tuple[int, ...]] = {  # 半音オフセット
    "maj": (0, 4, 7),
    "min": (0, 3, 7),
    "dim": (0, 3, 6),
    "maj7": (0, 4, 7, 11),
    "m7": (0, 3, 7, 10),
    "dom7": (0, 4, 7, 10),
}
