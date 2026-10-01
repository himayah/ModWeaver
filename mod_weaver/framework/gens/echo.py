"""残響もどき（FRAMEWORK_REDESIGN.md §7 の ``Echo``）。現行 ``band_common.echo()`` と同じ規則: パートの
``follow`` の NoteEvent を ``delay`` step 遅らせ、音量を ``ratio^k`` 倍にして写す。区間の外に出るものは
捨てる。``dur``（NoteOff も）をそのまま写すので、現行の ``offs=True`` に相当する動作が既定になる。"""
from __future__ import annotations

from ..context import Generator, SectionCtx
from ..score import NoteEvent, NoteOff


class Echo(Generator):
    def __init__(self, delay: int = 3, ratio: float = 0.5, repeats: int = 1) -> None:
        self.delay = delay
        self.ratio = ratio
        self.repeats = repeats

    def section(self, ctx: SectionCtx) -> None:
        src = ctx.events_of(ctx.part.follow)
        limit = ctx.plan.steps
        used: set[int] = set()
        for e in src:
            for k in range(1, self.repeats + 1):
                step = e.step + self.delay * k
                if step >= limit or step in used:
                    continue
                if isinstance(e, NoteEvent):
                    vel = None if e.vel is None else max(1, round(e.vel * self.ratio ** k))
                    ctx.note(step, e.inst, e.pitch, vel, dur=e.dur, chord=e.chord, strum_ms=e.strum_ms,
                             arts=e.arts)
                    used.add(step)
                elif isinstance(e, NoteOff):
                    ctx.off(step, e.inst)
                    used.add(step)
