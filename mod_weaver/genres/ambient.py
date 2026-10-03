"""ambient（旧 genres/ambient.py の宣言を機械変換したもの。DESIGN.md §6）。"""
from __future__ import annotations

from ..core.model import ChordSpec, GmVoice
from ..core.synth_presets import PRESETS
from ..framework.gens import Echo, Pad
from ..framework.genre import Genre, Harmony, Instrument, Kit, Part, Section
from ..framework.context import Generator, MeasureCtx
from ..core.pitch import fold_into_range
from ..framework.registry import register_genre

C = ChordSpec


def _inst(key: str, gm: GmVoice, **changes) -> Instrument:
    patch = PRESETS[key]
    if changes:
        import dataclasses
        patch = dataclasses.replace(patch, **changes)
    return Instrument(patch=patch, gm=gm)

PROGRESSIONS = (
    ("Imaj7", (C(0, "maj7", label="Imaj7"),)),
    ("IVmaj7", (C(5, "maj7", label="IVmaj7"),)),
    ("vi(add9)", (C(9, "m9", label="vi9"),)),
)


GLASS_REGISTER = (19, 30)
BELL_REGISTER = (24, 35)


def _pcs(m: MeasureCtx) -> list[int]:
    chord = m.m.chord
    return sorted({t % 12 for t in chord.chord_tones}, key=lambda pc: (pc - chord.harmony) % 12)


class GlassHold(Generator):
    """区間の頭（4小節ごと）に、パッドとは別の構成音（第3音か第7音）を上で伸ばす（旧 extra_measure）。
    鳴らさない区間で前の音を止める処理は Realizer の責任（DESIGN.md §7.6）なので書かない。"""

    def __init__(self, inst: str, register: tuple[int, int]) -> None:
        self.inst = inst
        self.register = register

    def measure(self, m: MeasureCtx) -> None:
        if m.m.index != 0:
            return
        pcs = _pcs(m)
        pc = m.rng.choice(pcs[1:2] + pcs[3:4]) if len(pcs) > 3 else pcs[-1]
        m.note(0, self.inst, fold_into_range(pc, *self.register), vel=m.scale_vol(36))


class SparseBell(Generator):
    """まばらなベル: 小節ごとに確率で1音（bloom は1音多い）。"""

    def __init__(self, inst: str, register: tuple[int, int]) -> None:
        self.inst = inst
        self.register = register

    def measure(self, m: MeasureCtx) -> None:
        n = 1 if m.rng.random() < 0.6 else 0
        if m.plan.kind == "bloom":
            n += 1
        lo, hi = self.register
        pcs = set(_pcs(m))
        tones = [t for t in range(lo, hi + 1) if t % 12 in pcs]
        vol = round(m.scale_vol(36) * 0.9)
        for step in sorted(m.rng.sample((0, 4, 6, 8, 10), k=n)):
            m.note(step, self.inst, m.rng.choice(tones), vel=vol)


@register_genre
class AmbientGenre(Genre):
    id = "ambient"
    display_name = "Ambient"
    description = "アンビエント。拍の弱い、重なり合うパッドとまばらなベル"
    description_en = "Ambient: layered pads and sparse bells with little or no beat"
    title = "Ambient Layers"
    tempo_choices = (60, 64, 68, 72)

    instruments = {
        "glass": _inst("pad_glass", GmVoice(program=88)),
        "bell": _inst("keys_bell", GmVoice(program=9)),
        "pad": _inst("pad_warm", GmVoice(program=89)),
    }
    harmony = Harmony(keys=(2, 4), mode="lydian", progressions=PROGRESSIONS, n_progressions=3)
    sections = {
        "layer1": Section(intensity=0.3, parts=frozenset({"pad"})),
        "layer2": Section(prog=1, intensity=0.5, parts=frozenset({"bell", "glass", "pad"})),
        "bloom": Section(prog=2, intensity=0.8, parts=frozenset({"bell", "glass", "pad"})),
        "drift": Section(intensity=0.5, parts=frozenset({"bell", "glass"})),
        "fade": Section(intensity=0.2, parts=frozenset({"pad"})),
    }
    form = ("layer1", "layer2", "bloom", "layer2", "drift", "fade")
    parts = (
        Part("pad", Pad("pad", vol=34), pan=128),
        Part("glass", GlassHold("glass", GLASS_REGISTER), pan=128),
        Part("bell", SparseBell("bell", BELL_REGISTER), pan=128),
        Part("bell echo", Echo(delay=5, ratio=0.5, repeats=2), follow="bell", pan=128),
    )
    mod_channels = {4: 1}
