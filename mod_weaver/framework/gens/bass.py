"""ベースの型（DESIGN.md §5.8 の ``BassLine``）。現行 ``band_common.bass_line()`` と同じ値・
規則で、座標を row ではなく step で書く。register は ``Genre.harmony.registers.bass`` から取る。"""
from __future__ import annotations

from ...core.pitch import fold_into_range
from ...errors import PlanError
from ..context import Generator, MeasureCtx
from ._common import scaled_step


class BassLine(Generator):
    def __init__(self, inst: str, kind: str = "root8", vol: int = 54) -> None:
        self.inst = inst
        self.kind = kind
        self.vol = vol

    def measure(self, m: MeasureCtx) -> None:
        register = m.genre.harmony.registers.bass
        for row, note, vol in _bass_line(self.kind, m.m.chord, m.m.steps, register, m.rng, self.vol):
            m.note(row, self.inst, m.pitch_for(self.inst, note), vel=m.scale_vol(vol))


def _bass_line(kind: str, chord, steps: int, register: tuple[int, int], rng, vol: int
               ) -> list[tuple[int, float, int]]:
    """``(step, logical note, vol)`` の列。16 step（4/4）基準の型を小節の step 数に比例させる。"""
    root = chord.bass
    fifth = fold_into_range(root + 7, *register)
    octave = root + 12 if root + 12 <= register[1] + 12 else root

    def at(r16: float) -> int:
        return scaled_step(r16, steps)

    if kind == "whole":
        return [(0, root, vol)]
    if kind == "half":
        return [(0, root, vol), (at(8), fifth if rng.random() < 0.4 else root, vol - 4)]
    if kind == "root8":
        return [(at(r), root, vol if r % 4 == 0 else vol - 8) for r in range(0, 16, 2)]
    if kind == "octave8":
        return [(at(r), root if (r // 2) % 2 == 0 else fold_into_range(root + 12, register[0], register[1] + 12),
                 vol if r % 4 == 0 else vol - 6) for r in range(0, 16, 2)]
    if kind == "offbeat":
        return [(at(r), root, vol) for r in (2, 6, 10, 14)]
    if kind == "rootfifth":
        return [(0, root, vol), (at(8), fifth, vol - 4)]
    if kind == "bossa":
        return [(0, root, vol), (at(6), fifth, vol - 6), (at(8), fifth, vol - 4), (at(14), root, vol - 8)]
    if kind == "walking":
        tones = sorted({t % 12 for t in chord.chord_tones})
        third = fold_into_range(root + ((tones[1] - root) % 12 if len(tones) > 1 else 4), *register)
        approach = fold_into_range(root + (1 if rng.random() < 0.5 else -1) + 7, *register)
        return [(at(0), root, vol), (at(4), third, vol - 6), (at(8), fifth, vol - 4), (at(12), approach, vol - 8)]
    if kind == "synco16":
        pat = [(0, root), (3, octave), (6, root), (8, fifth), (11, octave), (14, root)]
        return [(at(r), fold_into_range(n, register[0], register[1] + 12), vol if r in (0, 8) else vol - 8)
                for r, n in pat if r in (0, 8) or rng.random() < 0.75]
    if kind == "boombap":
        return [(0, root, vol), (at(3), root, vol - 10), (at(10), fifth if rng.random() < 0.5 else root, vol - 4)]
    if kind == "pulse16":
        b2 = fold_into_range(root + 1, *register)
        cycle = (root, root, b2, root, fifth, root, b2, root)
        return [(r, cycle[i % len(cycle)], vol if r % 4 == 0 else vol - 10) for i, r in enumerate(range(0, steps))]
    if kind == "house":
        return [(at(r), n, vol if r == 0 else vol - 6)
                for r, n in ((0, root), (3, octave), (7, root), (10, fifth), (14, root))]
    raise PlanError(f"unknown bass kind: {kind!r}")
