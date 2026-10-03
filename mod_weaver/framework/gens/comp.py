"""和音の刻み（DESIGN.md §5.8 の ``Comp``）。現行 ``band_common.comp()``・``comp_rows()`` と
同じ値・規則で、座標を row ではなく step で書く。"""
from __future__ import annotations

from ...core.pitch import CHORD_QUALITIES
from ...errors import PlanError
from ..context import Generator, MeasureCtx
from ..score import Vibrato
from ._common import arp_tones, scaled_step


class Comp(Generator):
    def __init__(self, inst: str, kind: str = "whole", vol: int = 44, *, chordal: bool = True,
                 wobble: int = 0, strum_ms: float = 0.0) -> None:
        self.inst = inst
        self.kind = kind
        self.vol = vol
        self.chordal = chordal
        self.wobble = wobble
        self.strum_ms = strum_ms

    def measure(self, m: MeasureCtx) -> None:
        rows = _comp_rows(self.kind, m.m.steps, m.rng)
        chord = m.m.chord
        wobble_arts = (Vibrato(self.wobble, at=1, steps=1),) if self.wobble else ()
        if self.chordal:
            intervals = CHORD_QUALITIES[m.m.quality]
            for row, accent in rows:
                vol = m.scale_vol(self.vol if accent else max(1, self.vol - 10))
                m.note(row, self.inst, m.pitch_for(self.inst, chord.harmony), vel=vol,
                       chord=intervals if m.pitch_for(self.inst, 0) is not None else (), strum_ms=self.strum_ms,
                       arts=wobble_arts)
        else:
            tones = arp_tones(chord, m.genre.harmony.registers.harmony)
            for i, (row, accent) in enumerate(rows):
                vol = m.scale_vol(self.vol if accent else max(1, self.vol - 10))
                m.note(row, self.inst, m.pitch_for(self.inst, tones[i % len(tones)]), vel=vol, arts=wobble_arts)


def _comp_rows(kind: str, steps: int, rng) -> list[tuple[int, bool]]:
    """和音を鳴らす ``(step, 強勢か)`` の列。16 step 基準の型を小節の step 数に比例させる。"""
    def at(r16: float) -> int:
        return scaled_step(r16, steps)

    table = {
        "whole": [(0, True)],
        "half": [(0, True), (8, False)],
        "pulse4": [(0, True), (4, False), (8, True), (12, False)],
        "pulse8": [(r, r % 8 == 0) for r in range(0, 16, 2)],
        "offbeat": [(r, True) for r in (2, 6, 10, 14)],
        "charleston": [(0, True), (6, False)],
        "strum": [(0, True), (4, True), (6, False), (10, False), (12, True), (14, False)],
        "bossa": [(0, True), (3, False), (6, False), (10, True), (12, False)],
        "stab2": [(3, True), (10, True)],
        "arp8": [(r, r % 8 == 0) for r in range(0, 16, 2)],
        "arp16": [(r, r % 4 == 0) for r in range(16)],
        "fingerpick": [(r, r % 4 == 0) for r in range(0, 16, 2)],
    }
    if kind == "cutting16":
        return [(at(r), r in (4, 12)) for r in range(16) if r in (4, 12) or rng.random() < 0.55]
    if kind not in table:
        raise PlanError(f"unknown comp kind: {kind!r}")
    return [(at(r), a) for r, a in table[kind]]
