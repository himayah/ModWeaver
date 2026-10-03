"""classical（旧 genres/classical.py の宣言を機械変換したもの。FRAMEWORK_REDESIGN.md §15）。"""
from __future__ import annotations

from ..core.composer import RhythmMotif, ScaleRules
from ..core.model import ChordSpec, GmVoice
from ..core.synth_presets import PRESETS
from ..framework.gens import Lead
from ..framework.genre import Genre, Harmony, Instrument, Kit, Part, Section
from ..framework.plan import Meter
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

LEAD_MOTIFS = {
    "minuet": (RhythmMotif(rows=(0, 4, 8)), RhythmMotif(rows=(0, 2, 4, 8)), RhythmMotif(rows=(0, 4, 6, 8)), RhythmMotif(rows=(0, 6, 8))),
    "trio": (RhythmMotif(rows=(0, 8)), RhythmMotif(rows=(0, 4, 8)), RhythmMotif(rows=(0, 2, 4, 6, 8))),
}
METER = Meter(12, 4, (3, 4))
PROGRESSIONS = (
    ("antecedent I-IV-ii6-V", (C(0, "maj", label="I"), C(5, "maj", label="IV"), C(2, "min", bass=5, label="ii6"), C(7, "maj", label="V"))),
    ("consequent I-IV-V7-I", (C(0, "maj", label="I"), C(5, "maj", label="IV"), C(7, "dom7", label="V7"), C(0, "maj", label="I"))),
    ("dominant I-V/V-V7-I", (C(0, "maj", label="I"), C(2, "dom7", label="V/V"), C(7, "dom7", label="V7"), C(0, "maj", label="I"))),
    ("return I-vi-V/V-V", (C(0, "maj", label="I"), C(9, "min", label="vi"), C(2, "dom7", label="V/V"), C(7, "maj", label="V"))),
    ("trio I-V7-V7-I", (C(0, "maj", label="I"), C(7, "dom7", label="V7"), C(7, "dom7", label="V7"), C(0, "maj", label="I"))),
    ("trio IV-I-V7-I", (C(5, "maj", label="IV"), C(0, "maj", label="I"), C(7, "dom7", label="V7"), C(0, "maj", label="I"))),
    ("coda IV-V7-I-I", (C(5, "maj", label="IV"), C(7, "dom7", label="V7"), C(0, "maj", label="I"), C(0, "maj", label="I"))),
)


VLN2_REGISTER = (17, 28)
VLA_REGISTER = (10, 21)


def _nearest(state: dict, name: str, pcs, register: tuple[int, int], avoid=None) -> int:
    """直前の音に最も近い構成音（声部の滑らかな進行）。直前の音は区間の state に持つ。"""
    lo, hi = register
    cands = [n for n in range(lo, hi + 1) if n % 12 in pcs and n % 12 != avoid] or             [n for n in range(lo, hi + 1) if n % 12 in pcs]
    prev = state.get(name, (lo + hi) // 2)
    note = min(cands, key=lambda n: (abs(n - prev), n))
    state[name] = note
    return note


class InnerVoices(Generator):
    """vln2・vla: 2・3拍目に和音を刻む（メヌエットの伴奏型）。最後の小節は1拍目に和音を伸ばす（旧 compose_measure）。
    刻みの切れ目（次の小節の1拍目の前で止める）は dur で書く。"""

    def measure(self, m: MeasureCtx) -> None:
        final = m.plan.kind == "coda" and m.is_last
        tones = sorted({t % 12 for t in m.m.chord.chord_tones})
        upper = _nearest(m.state, "vln2", tones, VLN2_REGISTER)
        inner = _nearest(m.state, "vla", tones, VLA_REGISTER, avoid=upper % 12)
        steps = (0,) if final else (4, 8)
        for step in steps:
            dur = m.m.steps - 1 - step if (not final and step == steps[-1]) else None
            m.note(step, "vln2", upper, vel=m.scale_vol(34), dur=dur)
            m.note(step, "vla", inner, vel=m.scale_vol(34), dur=dur)


class Cello(Generator):
    """vc: 1拍目に低音。トリオは3拍目にも5度（終止の小節は1拍目だけを伸ばす）。"""

    def __init__(self, inst: str) -> None:
        self.inst = inst

    def measure(self, m: MeasureCtx) -> None:
        final = m.plan.kind == "coda" and m.is_last
        chord = m.m.chord
        m.note(0, self.inst, chord.bass, vel=m.scale_vol(48))
        if m.plan.section.motifs == "trio" and not final:
            m.note(8, self.inst, fold_into_range(chord.bass + 7, *m.genre.harmony.registers.bass), vel=m.scale_vol(40))


@register_genre
class ClassicalGenre(Genre):
    id = "classical"
    display_name = "Classical (String Quartet)"
    description = "クラシック。古典派のメヌエット風の弦楽四重奏、明確な和声と終止"
    description_en = "Classical: a Classical-era minuet for string quartet with clear cadences"
    title = "Minuet and Trio"
    tempo_choices = (100, 104, 108, 112, 116, 120)

    instruments = {
        "vln1": _inst("orch_violin", GmVoice(program=48)),
        "vln2": _inst("orch_violin", GmVoice(program=40), name="OrchViolin2", volume=38),
        "vla": _inst("orch_viola", GmVoice(program=48), volume=38),
        "vc": _inst("orch_cello", GmVoice(program=42)),
    }
    harmony = Harmony(keys=(7, 2, 5, 10), mode="ionian", progressions=PROGRESSIONS, n_progressions=2, fixed=True)
    sections = {
        "ante": Section(intensity=0.7, parts=frozenset({"inner", "bass", "lead"}), motifs="minuet", meter=METER),
        "cons": Section(prog=1, intensity=0.75, parts=frozenset({"inner", "bass", "lead"}), motifs="minuet", meter=METER),
        "dom": Section(prog=2, intensity=0.85, parts=frozenset({"inner", "bass", "lead"}), key_offset=7, motifs="minuet", meter=METER),
        "ret": Section(prog=3, intensity=0.8, parts=frozenset({"inner", "bass", "lead"}), motifs="minuet", meter=METER),
        "trio_a": Section(prog=4, intensity=0.55, parts=frozenset({"inner", "bass", "lead"}), key_offset=5, motifs="trio", meter=METER),
        "trio_b": Section(prog=5, intensity=0.6, parts=frozenset({"inner", "bass", "lead"}), key_offset=5, motifs="trio", meter=METER),
        "coda": Section(prog=6, intensity=0.8, parts=frozenset({"inner", "bass", "lead"}), motifs="minuet", meter=METER),
    }
    form = ("ante", "cons", "ante", "cons", "dom", "ret", "ante", "cons", "trio_a", "trio_b", "trio_a", "trio_b", "ante", "cons", "coda")
    parts = (
        Part("lead", Lead("vln1", ScaleRules(leap_probability=0.2, leap_semitones=(3, 4, 5, 7, 8, 12)), LEAD_MOTIFS,
                   vol=46, gate=0.9, vibrato=0x22), pan=128),
        Part("inner", InnerVoices(), pan=128,
             kit=Kit(groups=(("violin 2", ("vln2",)), ("viola", ("vla",))))),
        Part("bass", Cello("vc"), pan=128),
    )
    mod_channels = {4: 1}
