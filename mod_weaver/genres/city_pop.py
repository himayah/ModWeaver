"""city-pop（旧 genres/city_pop.py の宣言を機械変換したもの。DESIGN.md §6）。"""
from __future__ import annotations

from ..core.composer import RhythmMotif, ScaleRules
from ..core.model import ChordSpec, GmVoice
from ..core.synth_presets import PRESETS
from ..framework.gens import BassLine, Comp, Echo, Groove, Layer, Lead, hits
from ..framework.genre import Genre, Harmony, Instrument, Kit, Part, Section
from ..framework.context import Generator, MeasureCtx
from ..core.pitch import CHORD_QUALITIES
from ..framework.registry import register_genre

C = ChordSpec


def _inst(key: str, gm: GmVoice, **changes) -> Instrument:
    patch = PRESETS[key]
    if changes:
        import dataclasses
        patch = dataclasses.replace(patch, **changes)
    return Instrument(patch=patch, gm=gm)

GROOVES = {
    "main": hits("kick", (0, 7, 10), 56) + hits("snare", (4, 12), 48) + hits("hat", (0, 2, 4, 6, 8, 10, 12, 14), 28) + hits("tamb", (4, 12), 24),
    "fill": hits("snare", (10, 12, 13, 14, 15), 44),
    "crash": hits("crash", (0,), 50),
}
LEAD_MOTIFS = {
    "verse": (RhythmMotif(rows=(0, 3, 6, 8, 12)), RhythmMotif(rows=(2, 4, 7, 10, 12)), RhythmMotif(rows=(0, 4, 6, 10, 14))),
    "chorus": (RhythmMotif(rows=(0, 2, 4, 7, 10, 12)), RhythmMotif(rows=(0, 3, 6, 8, 10, 14))),
}
PROGRESSIONS = (
    ("IVmaj7-III7-vi7-v7", (C(5, "maj7", label="IVmaj7"), C(4, "dom7", label="III7"), C(9, "m7", label="vi7"), C(7, "m7", label="v7"))),
    ("ii7-V7-Imaj7-VI7", (C(2, "m7", label="ii7"), C(7, "dom7", label="V7"), C(0, "maj7", label="Imaj7"), C(9, "dom7", label="VI7"))),
    ("IVmaj7-V7-iii7-vi7", (C(5, "maj7", label="IVmaj7"), C(7, "dom9", label="V9"), C(4, "m7", label="iii7"), C(9, "m9", label="vi9"))),
)


class HalfPad(Generator):
    """エレピは2拍ごとに和音（テンションコード）を置く（旧 pad の上書き）。"""

    def __init__(self, inst: str, vol: int) -> None:
        self.inst = inst
        self.vol = vol

    def measure(self, m: MeasureCtx) -> None:
        for step, vol in ((0, self.vol), (8, self.vol - 8)):
            if step < m.m.steps:
                m.note(step, self.inst, m.m.chord.harmony, vel=m.scale_drum(vol), chord=CHORD_QUALITIES[m.m.quality])


@register_genre
class CityPopGenre(Genre):
    id = "city-pop"
    display_name = "City Pop"
    description = "シティポップ。テンションコードのエレピ、跳ねるベースとギターのカッティング"
    description_en = "City pop: jazzy electric piano, bouncy bass and funky guitar cutting"
    title = "City Pop Night"
    tempo_choices = (104, 108, 112, 116, 120)

    instruments = {
        "kick": _inst("drum_pop_kick", GmVoice(drum_note=36)),
        "snare": _inst("drum_pop_snare", GmVoice(drum_note=38)),
        "hat": _inst("nostalgic_hihat", GmVoice(drum_note=42)),
        "tamb": _inst("perc_tambourine", GmVoice(drum_note=54)),
        "crash": _inst("march_crash_cymbal", GmVoice(drum_note=49)),
        "bass": _inst("bass_slap", GmVoice(program=36)),
        "lead": _inst("syn_brass", GmVoice(program=62)),
        "line": _inst("orch_violin", GmVoice(program=48), volume=30),
        "ep": _inst("keys_ep", GmVoice(program=4)),
        "cut": _inst("gtr_clean_cut", GmVoice(program=28)),
    }
    harmony = Harmony(keys=(4, 9, 1), mode="ionian", mode_by_quality={"m7": "dorian", "dom7": "mixolydian"}, progressions=PROGRESSIONS, n_progressions=3)
    sections = {
        "intro": Section(intensity=0.7, parts=frozenset({"pad", "bass", "drums", "comp"}), crash=True),
        "verse": Section(prog=1, intensity=0.7, parts=frozenset({"bass", "drums", "comp", "pad", "lead"})),
        "pre": Section(prog=2, intensity=0.8, parts=frozenset({"bass", "drums", "comp", "pad", "lead"}), fill=True),
        "chorus": Section(intensity=1.0, parts=frozenset({"bass", "drums", "comp", "pad", "lead"}), fill=True, crash=True, motifs="chorus"),
        "interlude": Section(prog=1, intensity=0.6, parts=frozenset({"bass", "drums", "comp"})),
        "outro": Section(intensity=0.6, parts=frozenset({"pad", "bass", "drums", "comp"})),
    }
    form = ("intro", "verse", "pre", "chorus", "interlude", "verse", "pre", "chorus", "chorus", "outro")
    parts = (
        Part("drums", Groove(GROOVES), pan=128,
             kit=Kit(groups=(("kick/snare", ("kick", "snare")), ("hat", ("hat", "tamb", "crash"))),
                     priority={"snare": 2, "crash": 3, "tamb": 2},
                     single_priority={"kick": 3, "snare": 4, "hat": 1, "tamb": 2, "crash": 2},
                     group_pan={"hat": 164})),
        Part("bass", BassLine("bass", kind="synco16", vol=56), pan=128),
        Part("pad", HalfPad("ep", vol=42), pan=84),
        Part("lead", Lead("lead", ScaleRules(leap_semitones=(3, 4, 5, 7), dissonance_weight=0.08), LEAD_MOTIFS,
                   vol=46, gate=0.8), pan=172),
        Part("comp", Comp("cut", kind="cutting16", vol=34), pan=48, min_channels=6),
        Part("lead echo", Echo(delay=3, ratio=0.45), follow="lead", pan=96, min_channels=8),
        Part("strings", Layer("line", vol=26, register=(19, 31)), follow="lead", pan=160, min_channels=8),
    )
    mod_channels = {4: 1, 6: 2, 8: 1}
