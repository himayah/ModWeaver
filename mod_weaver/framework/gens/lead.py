"""旋律（FRAMEWORK_REDESIGN.md §7 の ``Lead``）。現行 ``band_common.lead()``・``begin_pattern()`` と同じ
4小節の楽節（A・A・B・終止）。区間ごとに ``MelodyGenerator`` と動機 A・B を新しく選ぶ（区間をまたいで
旋律の終端音を引き継がない。現行どおり）。"""
from __future__ import annotations

import dataclasses
from typing import Callable, Mapping, Optional

from ...core.composer import MelodyGenerator, RhythmMotif, ScaleRules
from ..context import Generator, MeasureCtx, SectionCtx
from ..plan import SectionPlan
from ..score import Vibrato


class Lead(Generator):
    def __init__(self, inst: str, rules: ScaleRules, motifs: Mapping[str, tuple[RhythmMotif, ...]],
                 vol: int = 48, gate: float = 0.9, *, vibrato: int = 0,
                 inst_for: Optional[Callable[[SectionPlan], str]] = None) -> None:
        self.inst = inst
        self.rules = rules
        self.motifs = motifs
        self.vol = vol
        self.gate = gate
        self.vibrato = vibrato
        self.inst_for = inst_for

    def section(self, ctx: SectionCtx) -> None:
        reg = ctx.genre.harmony.registers.melody
        ctx.state["gen"] = MelodyGenerator(self.rules, reg, ctx.plan.scale, ctx.rng, base_vol=self.vol,
                                            beat_rows=ctx.plan.meter.steps_per_beat)
        pool = self.motifs[ctx.plan.section.motifs]
        ctx.state["motif_a"] = ctx.rng.choice(pool)
        ctx.state["motif_b"] = ctx.rng.choice(pool)
        ctx.state["prev"] = None
        for m in ctx.measures():
            self.measure(m)

    def measure(self, m: MeasureCtx) -> None:
        phrase_pos = m.m.index % 4
        motif = m.state["motif_a"] if phrase_pos in (0, 1) else m.state["motif_b"]
        cadence = phrase_pos == 3
        if cadence:
            half = m.m.steps // 2
            motif = RhythmMotif(tuple(r for r in motif.rows if r < half) or (0,))
        events, m.state["prev"] = m.state["gen"].bar(
            motif, m.m.chord, m.state["prev"], cadence=cadence, rows=m.m.steps, base_vol=m.scale_vol(self.vol))
        if cadence:
            events = [dataclasses.replace(e, dur=min(e.dur, m.m.steps // 2 - e.row)) for e in events]
            events = [e for e in events if e.dur > 0]
        inst = self.inst_for(m.plan) if self.inst_for is not None else self.inst
        for e in events:
            dur = max(1, round(e.dur * self.gate))
            arts = (Vibrato(self.vibrato, at=2),) if (self.vibrato and e.dur >= 6) else ()
            m.note(e.row, inst, e.note, vel=e.vol, dur=dur, arts=arts)
