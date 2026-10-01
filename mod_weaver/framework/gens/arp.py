"""アルペジオ（FRAMEWORK_REDESIGN.md §7 の ``Arp``）。現行 ``band_common.arp()`` と同じ規則。"""
from __future__ import annotations

from ..context import Generator, MeasureCtx
from ._common import arp_tones

DEFAULT_STEPS = tuple(range(0, 16, 2))


class Arp(Generator):
    def __init__(self, inst: str, register: tuple[int, int], steps: tuple[int, ...] = DEFAULT_STEPS,
                 vol: int = 38, *, pattern: str = "up") -> None:
        self.inst = inst
        self.register = register
        self.steps = steps
        self.vol = vol
        self.pattern = pattern

    def measure(self, m: MeasureCtx) -> None:
        tones = arp_tones(m.m.chord, self.register)
        if self.pattern == "updown" and len(tones) > 2:
            tones = tones + tones[-2:0:-1]
        for i, row in enumerate(r for r in self.steps if r < m.m.steps):
            vol = m.scale_vol(self.vol if i % 4 == 0 else max(1, self.vol - 6))
            m.note(row, self.inst, tones[i % len(tones)], vel=vol)
