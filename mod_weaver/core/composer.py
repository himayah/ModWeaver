"""作曲補助: リズム動機・旋律生成・配置とダイナミクス（DESIGN.md §4.3）。

Nostalgic は本モジュールを使わず、旧アルゴリズムを ``genres/nostalgic.py`` に移植している（DESIGN.md §6.1）。
"""
from __future__ import annotations

import dataclasses
import random
from dataclasses import dataclass
from typing import Optional, Sequence

from ..errors import PlanError
from .model import CellGrid, ChordDef, Instrument
from .pitch import Scale, fold_into_range


# ============================================================
# リズム動機
# ============================================================

@dataclass(frozen=True)
class RhythmMotif:
    """measure 内の発音 row の集合と各音の長さ。

    ``lengths`` 省略時は「次の発音（または measure 末）まで」。休符を作る場合のみ明示する
    （例: ``rows=(0,4), lengths=(3,3)``）。
    """

    rows: tuple[int, ...]
    lengths: Optional[tuple[int, ...]] = None

    def __post_init__(self) -> None:
        if not self.rows or any(b <= a for a, b in zip(self.rows, self.rows[1:])) or self.rows[0] < 0:
            raise PlanError(f"RhythmMotif.rows must be non-empty, non-negative and strictly increasing: {self.rows}")
        if self.lengths is not None and (
            len(self.lengths) != len(self.rows) or any(x < 1 for x in self.lengths)
        ):
            raise PlanError(f"RhythmMotif.lengths must match rows and be >= 1: {self.lengths}")

    def durations(self, measure_rows: int) -> tuple[int, ...]:
        if self.rows[-1] >= measure_rows:
            raise PlanError(f"motif row {self.rows[-1]} is outside the measure ({measure_rows} rows)")
        if self.lengths is not None:
            return self.lengths
        ends = list(self.rows[1:]) + [measure_rows]
        return tuple(e - r for r, e in zip(self.rows, ends))


@dataclass(frozen=True)
class NoteEvent:
    row: int
    note: int         # logical note
    vol: int
    dur: int          # 発音の長さ（row）。motif.lengths、なければ次の発音（または measure 末）まで


# ============================================================
# 旋律生成
# ============================================================

@dataclass(frozen=True)
class ScaleRules:
    step_choices: tuple[int, ...] = (-1, 1, -2, 2)  # スケール上の段数（順次進行）
    leap_probability: float = 0.25                  # 経過音で跳躍を選ぶ確率
    leap_semitones: tuple[int, ...] = ()            # 跳躍として許可する音程（空=任意のコードトーン）
    max_leap: int = 12                              # 半音
    leap_recovery: bool = True                      # 跳躍後は逆方向の順次進行を強制
    dissonance_weight: float = 0.0                  # 弱拍でコード外音を置く確率
    color_semitones: tuple[int, ...] = (1, 6)       # dissonance 時にコード音との距離として選ぶ音程
    strong_nearest_prob: float = 0.75               # 強拍で「直前音に最も近いコードトーン」を選ぶ確率


BEAT_ROWS = 4          # 1 拍 = 4 row（16 分格子。既定の timebase）
LEAP_THRESHOLD = 5     # 跳躍枝で選ばれた移動、またはこの半音数以上の移動を「跳躍」とみなす（leap_recovery の判定）


class MelodyGenerator:
    """共通の旋律ジェネレータ。``rules`` と音域で挙動を制御する。"""

    def __init__(
        self,
        rules: ScaleRules,
        register: tuple[int, int],
        scale: Scale,
        rng: random.Random,
        base_vol: int = 50,
        beat_rows: int = BEAT_ROWS,
    ) -> None:
        self.rules = rules
        self.register = register
        self.scale = scale
        self.rng = rng
        self.base_vol = base_vol
        self.beat_rows = beat_rows   # 1 拍の row 数（EXT-1: 1拍=2row の swing timebase 等で上書きする）
        self._recover: Optional[int] = None    # 跳躍直後の次の弱拍で進むべき向き（+1/−1）

    # --- 内部 ---
    def _fold(self, n: int) -> int:
        return fold_into_range(n, *self.register)

    def _pool(self, notes: Sequence[int], octave_shift: int) -> list[int]:
        return sorted({self._fold(n + 12 * octave_shift) for n in notes})

    def _strong(self, tones: list[int], prev: Optional[int]) -> int:
        if prev is None:
            return self.rng.choice(tones)
        ranked = sorted(tones, key=lambda n: (abs(n - prev), n))
        if len(ranked) > 1 and self.rng.random() >= self.rules.strong_nearest_prob:
            return ranked[1]
        return ranked[0]

    def _color(self, tones: list[int], scale_pool: list[int], prev: Optional[int]) -> int:
        """最寄りのコードトーンから ``color_semitones`` 離れた音（スケール音を優先）。"""
        anchor = tones[0] if prev is None else min(tones, key=lambda n: (abs(n - prev), n))
        lo, hi = self.register
        cands = sorted({anchor + s * d for s in self.rules.color_semitones for d in (1, -1)
                        if lo <= anchor + s * d <= hi})
        in_scale = [c for c in cands if c in scale_pool]
        pool = in_scale or cands
        return self.rng.choice(pool) if pool else anchor

    def _step(self, scale_pool: list[int], prev: int, direction: Optional[int] = None) -> int:
        """スケール上の順次進行。``direction`` を指定すると逆行の 1〜2 段（leap_recovery）。"""
        idx = min(range(len(scale_pool)), key=lambda i: (abs(scale_pool[i] - prev), scale_pool[i]))
        if direction is not None:
            step = direction * self.rng.choice((1, 2))
        else:
            step = self.rng.choice(self.rules.step_choices)
        return scale_pool[max(0, min(len(scale_pool) - 1, idx + step))]

    def _leap(self, tones: list[int], prev: int) -> Optional[int]:
        r = self.rules
        cands = [n for n in tones
                 if 3 <= abs(n - prev) <= r.max_leap and (not r.leap_semitones or abs(n - prev) in r.leap_semitones)]
        return self.rng.choice(cands) if cands else None

    # --- 公開 ---
    def bar(
        self,
        motif: RhythmMotif,
        chord: ChordDef,
        prev: Optional[int],
        *,
        cadence: bool = False,
        cadence_target: Optional[int] = None,
        octave_shift: int = 0,
        rows: int = 16,
        base_vol: Optional[int] = None,
    ) -> tuple[list[NoteEvent], int]:
        """1 measure 分の ``NoteEvent`` 列と終端音を返す。

        各 onset: ①強拍（``row % 4 == 0``）は ``chord_tones`` から直前音に近い順に選ぶ（確率 ``strong_nearest_prob`` で
        最近傍、他は次点）。②弱拍は確率 ``dissonance_weight`` でコード外の色音、なければ確率 ``1−leap_probability``
        で順次進行、残りで跳躍。③跳躍直後の弱拍は ``leap_recovery`` なら逆方向 1〜2 段。④``cadence`` の最終 onset は
        ``cadence_target``（無指定なら ``chord_tones[0]``）。⑤全音を音域内へ折返す。⑥音量は強拍=基準、弱拍=基準−(4〜12)。
        """
        r = self.rules
        vol0 = self.base_vol if base_vol is None else base_vol
        tones = self._pool(chord.chord_tones, octave_shift)
        scale_pool = self._pool(chord.scale_tones, octave_shift) or tones
        durs = motif.durations(rows)

        events: list[NoteEvent] = []
        current = prev
        last_idx = len(motif.rows) - 1
        for i, (row, dur) in enumerate(zip(motif.rows, durs)):
            strong = row % self.beat_rows == 0
            leaped = False
            if cadence and i == last_idx:
                target = cadence_target if cadence_target is not None else chord.chord_tones[0]
                note = self._fold(target + 12 * octave_shift)
                self._recover = None
            elif strong or current is None:
                note = self._strong(tones, current)
                self._recover = None
            elif self._recover is not None and r.leap_recovery:
                note = self._step(scale_pool, current, self._recover)
                self._recover = None
            elif self.rng.random() < r.dissonance_weight:
                note = self._color(tones, scale_pool, current)
                self._recover = None
            elif self.rng.random() >= r.leap_probability:
                note = self._step(scale_pool, current)
                self._recover = None
            else:
                leap = self._leap(tones, current)
                leaped = leap is not None
                note = leap if leaped else self._step(scale_pool, current)
                self._recover = None

            if current is not None and r.leap_recovery and (leaped or abs(note - current) >= LEAP_THRESHOLD):
                self._recover = -1 if note > current else 1
            vol = vol0 if strong else max(1, vol0 - self.rng.randint(4, 12))
            events.append(NoteEvent(row, note, min(64, vol), dur))
            current = note
        return events, current


# ============================================================
# 配置・ダイナミクス補助
# ============================================================

def ramp(v0: int, v1: int, i: int, n: int) -> int:
    """線形補間（``i=0..n-1`` で ``v0→v1``）。``n<=1`` なら ``v0``。"""
    if n <= 1:
        return v0
    return int(round(v0 + (v1 - v0) * i / (n - 1)))


def fade_cells(target: CellGrid, ch: int, r0: int, r1: int, v0: int, v1: int) -> None:
    """``r0..r1``（両端を含む）の既存セルの ``vol`` を ``v0→v1`` の線形補間で書き換える。

    ``vol`` を持たないセル（休符・エフェクト付き）は対象外。
    """
    n = r1 - r0 + 1
    for i, row in enumerate(range(r0, r1 + 1)):
        cell = target.get(row, ch)
        if cell.vol is not None:
            target.replace(row, ch, dataclasses.replace(cell, vol=max(0, min(64, ramp(v0, v1, i, n)))))


def articulate(
    buf: CellGrid,
    ch: int,
    events: Sequence[NoteEvent],
    inst: Instrument,
    *,
    gate: float = 1.0,
) -> None:
    """各 event を ``inst.cell(note, vol=vol)`` で置く。持続（ループ）音色向けに OFF も置く（D12）。

    ``off_row = row + max(1, round(dur × gate))`` が「measure 内」かつ「次の発音 row より前」のときだけ
    ``inst.off()`` を置く。``gate=1.0`` は休符（音価の終端が次の発音より前）があるときだけ、``gate<1`` はスタッカート。
    """
    for i, ev in enumerate(events):
        buf.put(ev.row, ch, inst.cell(ev.note, vol=ev.vol))
        next_row = events[i + 1].row if i + 1 < len(events) else buf.rows
        off_row = ev.row + max(1, round(ev.dur * gate))
        if off_row < buf.rows and off_row < next_row:
            buf.put(off_row, ch, inst.off())
