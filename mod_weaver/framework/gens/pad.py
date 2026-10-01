"""パッド（FRAMEWORK_REDESIGN.md §7 の ``Pad``）。現行 ``band_common.pad()`` と同じ規則: 和音の変わり目に
``dur=None``（次の発音まで＝ループなら区間の終わりまで鳴り続ける）だけ発音し直す。"""
from __future__ import annotations

from ...core.pitch import CHORD_QUALITIES
from ..context import Generator, MeasureCtx


class Pad(Generator):
    def __init__(self, inst: str, vol: int = 36, *, chordal: bool = True) -> None:
        self.inst = inst
        self.vol = vol
        self.chordal = chordal

    def measure(self, m: MeasureCtx) -> None:
        if not m.is_chord_change:
            return
        chord = m.m.chord
        intervals = CHORD_QUALITIES[m.m.quality] if self.chordal else ()
        m.note(0, self.inst, chord.harmony, vel=m.scale_vol(self.vol), chord=intervals, dur=None)
