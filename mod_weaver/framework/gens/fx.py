"""効果音の鳴らし直し（FRAMEWORK_REDESIGN.md §7 の ``Fx``）。現行 ``band_common`` の ``FxSpec`` 相当。
長い OneShot（vinyl・rain 等）を ``every`` 小節ごとに小節の先頭で鳴らし直す。"""
from __future__ import annotations

from ..context import Generator, MeasureCtx


class Fx(Generator):
    def __init__(self, inst: str, every: int = 2, vol: int = 20) -> None:
        self.inst = inst
        self.every = every
        self.vol = vol

    def measure(self, m: MeasureCtx) -> None:
        if m.m.index % self.every == 0:
            m.note(0, self.inst, vel=m.scale_vol(self.vol))
