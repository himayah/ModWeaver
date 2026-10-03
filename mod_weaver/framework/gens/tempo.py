"""テンポカーブ（FRAMEWORK_REDESIGN.md §7・§15.1 の ``TempoCurve``・``render_tempo_curve``）。

現行 ``core/automation.TempoCurve`` と同じ式。``ctx.tempo(step, bpm)`` を、BPM が変わる step にだけ呼ぶ
（同じ値が続く step は書かない）。Realizer が形式ごとに表現する（MOD・S3M・XM・IT は Fxx・Txx 等、MIDI は Set Tempo）。
"""
from __future__ import annotations

from typing import Optional

from ...errors import PlanError
from ..context import SectionCtx

KINDS = ("linear", "ease_in", "ease_out")


def _frac(kind: str, x: float) -> float:
    if kind == "ease_in":
        return x * x
    if kind == "ease_out":
        return 1.0 - (1.0 - x) ** 2
    return x


def tempo_curve(ctx: SectionCtx, start_bpm: int, end_bpm: int, start_step: int, end_step: int,
                kind: str = "linear") -> None:
    """``start_step``〜``end_step``（両端を含む）で ``start_bpm`` から ``end_bpm`` へ連続的に変える。"""
    if kind not in KINDS:
        raise PlanError(f"unknown tempo curve kind: {kind!r}")
    if not 0 <= start_step < end_step:
        raise PlanError(f"tempo_curve steps must satisfy 0 <= start_step < end_step: {start_step}, {end_step}")
    prev: Optional[int] = None
    for step in range(start_step, end_step + 1):
        x = (step - start_step) / (end_step - start_step)
        bpm = max(32, min(255, round(start_bpm + (end_bpm - start_bpm) * _frac(kind, x))))
        if bpm == prev:
            continue
        ctx.tempo(step, bpm)
        prev = bpm
