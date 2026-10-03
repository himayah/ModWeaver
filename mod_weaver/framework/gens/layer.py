"""任意パートの層（DESIGN.md §5.8 の ``Layer``）。現行 ``band_common.layer()``（``LayerSpec``）と
同じ規則: 和音の変わり目に、和音（``chordal``）か第3音相当の長音を置く。パートの ``follow`` で鳴る区間を
決める（DESIGN.md §5.1）ので、このジェネレータ自身は常に処理する。乱数は使わない。"""
from __future__ import annotations

from ...core.pitch import CHORD_QUALITIES, fold_into_range
from ..context import Generator, MeasureCtx


class Layer(Generator):
    def __init__(self, inst: str, vol: int = 30, *, chordal: bool = False,
                 register: tuple[int, int] = (14, 26)) -> None:
        self.inst = inst
        self.vol = vol
        self.chordal = chordal
        self.register = register

    def measure(self, m: MeasureCtx) -> None:
        if not m.is_chord_change:
            return
        chord = m.m.chord
        if self.chordal:
            m.note(0, self.inst, m.pitch_for(self.inst, chord.harmony), vel=m.scale_vol(self.vol),
                   chord=CHORD_QUALITIES[m.m.quality] if m.pitch_for(self.inst, 0) is not None else ())
        else:
            pcs = sorted({t % 12 for t in chord.chord_tones}, key=lambda pc: (pc - chord.harmony) % 12)
            note = fold_into_range(pcs[1] if len(pcs) > 1 else pcs[0], *self.register)
            m.note(0, self.inst, m.pitch_for(self.inst, note), vel=m.scale_vol(self.vol))
