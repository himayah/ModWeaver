"""テンポ＆ダイナミクス・オートメーション（CORE_EXTENSION_DESIGN §4.5、EXT-5）。

- ``TempoCurve``/``render_tempo_curve``: row 単位で BPM を連続的に変化させる（フリージャズのルバート、
  EDM のビルドアップ等）。``Pattern`` への直接アクセスを持つ既存フック ``finalize_pattern`` から呼ぶ
  （新規フックは不要）。``tempo_policy="profile"`` と組み合わせて使う。
- ``portamento_param``: ``3xx``（Tone Portamento）の speed param を計算する純粋関数（808グライド等）。

挿入は ``CellGrid.try_insert_command``（core/model.py）に委譲する。密な編成では空きチャンネルが無い
row がありうるため、``apply_swing``（core/groove.py, EXT-1）と同じくその row だけ静かにスキップする
（直前の BPM が persist）。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from ..errors import PlanError, SampleConstraintError
from .model import Pattern

log = logging.getLogger("mod_weaver")


@dataclass(frozen=True)
class TempoCurve:
    start_bpm: int
    end_bpm: int
    start_row: int
    end_row: int
    curve_type: str = "linear"     # "linear" | "ease_in"（frac**2） | "ease_out"（1-(1-frac)**2）

    def __post_init__(self) -> None:
        for b in (self.start_bpm, self.end_bpm):
            if not 32 <= b <= 255:
                raise SampleConstraintError(f"bpm out of range for Fxx: {b}")
        if not 0 <= self.start_row < self.end_row:
            raise PlanError(f"TempoCurve rows must satisfy 0 <= start_row < end_row: {self}")
        if self.curve_type not in ("linear", "ease_in", "ease_out"):
            raise PlanError(f"unknown curve_type: {self.curve_type!r}")


def _frac(curve: TempoCurve, row: int) -> float:
    x = (row - curve.start_row) / (curve.end_row - curve.start_row)
    if curve.curve_type == "ease_in":
        return x * x
    if curve.curve_type == "ease_out":
        return 1.0 - (1.0 - x) ** 2
    return x


def render_tempo_curve(pattern: Pattern, curve: TempoCurve) -> None:
    """``pattern`` の ``start_row..end_row`` に、``curve`` に従って変化する ``F BPM`` を挿入する。

    値が変化した row にのみ挿入する（同じ BPM が続く区間は書かない）。空きチャンネルが無い row は
    静かにスキップする（モジュール docstring 参照）。
    """
    prev_bpm: Optional[int] = None
    for row in range(curve.start_row, curve.end_row + 1):
        bpm = round(curve.start_bpm + (curve.end_bpm - curve.start_bpm) * _frac(curve, min(row, curve.end_row)))
        bpm = max(32, min(255, bpm))
        if bpm == prev_bpm:
            continue
        if not pattern.try_insert_command(row, 0x0F, bpm):
            log.debug("render_tempo_curve: no free channel at row %d, skipping (previous BPM persists)", row)
            continue
        prev_bpm = bpm


def portamento_param(period_start: int, period_target: int, rows: int, ticks_per_row: int = 6) -> int:
    """``3xx``（Tone Portamento）の speed param。``rows`` 行かけて ``period_start`` から
    ``period_target`` に到達するように、1 tick あたりの period 変化量を概算する（PT のポルタメントは
    tick 毎に period を ±param だけ動かす）。呼出し側が ``effect=3`` として渡す。
    """
    if rows < 0:
        raise SampleConstraintError(f"rows must be >= 0: {rows}")
    if ticks_per_row < 1:
        raise SampleConstraintError(f"ticks_per_row must be >= 1: {ticks_per_row}")
    total_ticks = max(1, rows * ticks_per_row)
    delta = abs(period_start - period_target)
    return max(1, min(255, round(delta / total_ticks)))
