"""音高の表現（DESIGN.md §3.1・§4.1）。

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
    "dorian": (0, 2, 3, 5, 7, 9, 10),
    "mixolydian": (0, 2, 4, 5, 7, 9, 10),
    "lydian": (0, 2, 4, 6, 7, 9, 11),
    "harmonic_minor": (0, 2, 3, 5, 7, 8, 11),
    "melodic_minor": (0, 2, 3, 5, 7, 9, 11),
    "major_pent": (0, 2, 4, 7, 9),
    "minor_pent": (0, 3, 5, 7, 10),
    "blues": (0, 3, 5, 6, 7, 10),
}

CHORD_QUALITIES: dict[str, tuple[int, ...]] = {  # 半音オフセット
    "maj": (0, 4, 7),
    "min": (0, 3, 7),
    "dim": (0, 3, 6),
    "maj7": (0, 4, 7, 11),
    "m7": (0, 3, 7, 10),
    "dom7": (0, 4, 7, 10),
    # 第３段階で追加（DESIGN.md §12.8 C1）。先頭3つ（根音・第3音相当・第5音相当）が voice() の
    # アルペジオ（0xy）になる。テンション入りの和音は構成音をそのまま並べる（9th は 14、11th は 17、13th は 21）
    "6": (0, 4, 7, 9),
    "m6": (0, 3, 7, 9),
    "maj9": (0, 4, 7, 11, 14),
    "m9": (0, 3, 7, 10, 14),
    "dom9": (0, 4, 7, 10, 14),
    "dom13": (0, 4, 7, 10, 14, 21),
    "m11": (0, 3, 7, 10, 14, 17),
    "add9": (0, 4, 7, 14),
    "sus2": (0, 2, 7),
    "sus4": (0, 5, 7),
    "7sus4": (0, 5, 7, 10),
    "m7b5": (0, 3, 6, 10),
    "dim7": (0, 3, 6, 9),
    "aug": (0, 4, 8),
}


# ============================================================
# マイクロチューニング（DESIGN.md §4.1、EXT-3）
# ============================================================

FINETUNE_CENTS = 100.0 / 12.8   # 1 finetune ステップ ≈ 7.8125 セント（-8..+7 の等間隔仕様。ProTracker規格）


@dataclass(frozen=True)
class MicroScale:
    """cents 単位（tonic からの相対）で定義する音律。度数ごとに 12-ET から外れてよい。
    具体的な音律定義（maqam rast 等）は各ジャンルモジュール側に置く（本クラスはデータ構造のみ）。"""

    tonic_pc: int
    degrees_cents: tuple[float, ...]   # 度数0=主音(0.0)から始まる、主音からの相対セント列

    def degree_cents(self, degree: int, octave: int = 0) -> float:
        """``degree``（0始まり、スケール外は自動でオクターブ折返し）の、tonic からの相対セント。"""
        return self.degrees_cents[degree % len(self.degrees_cents)] + 1200.0 * (
            octave + degree // len(self.degrees_cents)
        )

    def absolute_cents(self, degree: int, tonic_note: int, octave: int = 0) -> float:
        """``degree`` の、logical note 0（C-1）からの絶対セント（``resolve_micronote()`` へそのまま渡せる）。

        ``tonic_note``: この音律を実際に鳴らす主音の logical note（例: qarar を G2 に置くなら
        ``pitch.parse("G-2")`` 等で求めた値）。``tonic_pc`` は音律の「相対的な形」を表すだけで、
        実際にどのオクターブへ主音を置くかは呼出し側（プロファイル）が決める。
        """
        return tonic_note * 100.0 + self.degree_cents(degree, octave)


def resolve_micronote(cents_from_c0: float) -> tuple[int, int]:
    """logical note 0（C-1）からの絶対セント量 → (tracker/logical note t, finetune)。

    t = round(cents/100) の 12-ET 最近傍。残差 = cents - t*100 を finetune ステップに量子化
    （round(残差 / FINETUNE_CENTS)、-8..7 にクランプ）。t は呼出し側で NOTE_MIN..NOTE_MAX を検査する
    （既存 PitchRangeError を流用。本関数はクランプしない＝機械的単位変換のみ）。
    """
    t = round(cents_from_c0 / 100.0)
    residual = cents_from_c0 - t * 100.0
    ft = max(-8, min(7, round(residual / FINETUNE_CENTS)))
    return t, ft


def fine_portamento_param(period: int, cents: float) -> int:
    """現在の period に対し、目標セント差 ``cents`` に最も近づく E1x/E2x の param（0..15）を返す。
    符号は呼出し側（0x1=up/0x2=down）が選ぶ。1単位の効果は period 依存で非一様なため、
    目標 period（隣接 Period 表エントリからの線形補間）との差を都度計算する。
    """
    target_period = period * (2.0 ** (-cents / 1200.0))
    delta = abs(period - target_period)
    return max(0, min(15, round(delta)))   # PERIODS の隣接差は概ね数〜十数なので実用上 0..15 に収まる
