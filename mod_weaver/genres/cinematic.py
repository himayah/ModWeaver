"""cinematic（旧 genres/cinematic.py の宣言を機械変換したもの。DESIGN.md §6）。"""
from __future__ import annotations

from ..core.composer import RhythmMotif, ScaleRules
from ..core.model import ChordSpec, GmVoice
from ..core.synth_presets import PRESETS
from ..framework.gens import Arp, BassLine, Lead, Pad
from ..framework.genre import Genre, Harmony, Instrument, Kit, Part, Section
from ..framework.context import Generator, MeasureCtx
from ..core.pitch import CHORD_QUALITIES, fold_into_range
from ..framework.registry import register_genre

C = ChordSpec


def _inst(key: str, gm: GmVoice, **changes) -> Instrument:
    patch = PRESETS[key]
    if changes:
        import dataclasses
        patch = dataclasses.replace(patch, **changes)
    return Instrument(patch=patch, gm=gm)

LEAD_MOTIFS = {
    "verse": (RhythmMotif(rows=(0, 8)), RhythmMotif(rows=(0, 6, 8)), RhythmMotif(rows=(0, 4, 8, 12)), RhythmMotif(rows=(0, 12))),
}
PROGRESSIONS = (
    ("i-VI-III-VII", (C(0, "min", label="i"), C(8, "maj", label="VI"), C(3, "maj", label="III"), C(10, "maj", label="VII"))),
    ("VI-VII-i", (C(8, "maj", label="VI"), C(10, "maj", label="VII"), C(0, "min", label="i"), C(0, "min", label="i"))),
    ("III-VII-i-VI (relative major I-V-vi-IV)", (C(3, "maj", label="III"), C(10, "maj", label="VII"), C(0, "min", label="i"), C(8, "maj", label="VI"))),
)


HORN_REGISTER = (14, 26)


class ChordHold(Generator):
    """和音の変わり目に、和音サンプルを伸ばす（viola。旧 extra_measure）。"""

    def __init__(self, inst: str, vol: int) -> None:
        self.inst = inst
        self.vol = vol

    def measure(self, m: MeasureCtx) -> None:
        if m.is_chord_change:
            m.note(0, self.inst, m.m.chord.harmony, vel=m.scale_vol(self.vol), chord=CHORD_QUALITIES[m.m.quality])


class BassHold(Generator):
    """和音の変わり目に、コントラバスの低音（根音の1オクターブ下）を伸ばす。"""

    def __init__(self, inst: str, vol: int) -> None:
        self.inst = inst
        self.vol = vol

    def measure(self, m: MeasureCtx) -> None:
        if m.is_chord_change:
            m.note(0, self.inst, m.m.chord.bass - 12, vel=m.scale_vol(self.vol))


class HornThird(Generator):
    """和音の変わり目に、ホルンで第3音（根音の次の構成音）を伸ばす。"""

    def __init__(self, inst: str, vol: int) -> None:
        self.inst = inst
        self.vol = vol

    def measure(self, m: MeasureCtx) -> None:
        if m.is_chord_change:
            chord = m.m.chord
            third = sorted({t % 12 for t in chord.chord_tones}, key=lambda pc: (pc - chord.harmony) % 12)[1]
            m.note(0, "horn", fold_into_range(third, *HORN_REGISTER), vel=m.scale_vol(self.vol))


class Timpani(Generator):
    """ティンパニ: 区間の頭に1打（climax は8 step 目にもう1打）。rise2 は最後の小節でロール、その2小節前にシンバルのスウェル。"""

    def measure(self, m: MeasureCtx) -> None:
        bass = m.m.chord.bass
        kind = m.plan.kind
        if kind == "rise2" and m.is_last:
            for step in range(m.m.steps):                      # 最後の小節はティンパニのロールで高める
                m.note(step, "timp", bass, vel=min(64, 24 + step * 2))
        elif kind == "rise2" and m.m.index == 1:
            m.note(0, "swell", vel=40)                         # クライマックスの2小節前にシンバルのスウェル
        else:
            m.note(0, "timp", bass, vel=m.scale_vol(50))
            if kind == "climax":
                m.note(8, "timp", bass, vel=m.scale_vol(40))


@register_genre
class CinematicGenre(Genre):
    id = "cinematic"
    display_name = "Cinematic"
    description = "映画音楽。ピアノのオスティナートから弦とホルンが重なり、ドラマチックに高まる"
    description_en = "Cinematic: piano ostinato building to soaring strings and horns"
    title = "Cinematic Rise"
    tempo_choices = (70, 72, 76, 80, 84)

    instruments = {
        "piano": _inst("keys_piano", GmVoice(program=0), volume=42),
        "vln": _inst("orch_violin", GmVoice(program=48)),
        "vc": _inst("orch_cello", GmVoice(program=42)),
        "cb": _inst("orch_bass_str", GmVoice(program=43)),
        "horn": _inst("march_brass_section", GmVoice(program=61), volume=40),
        "timp": _inst("orch_timpani", GmVoice(program=47)),
        "swell": _inst("free_cymbal_swell", GmVoice(program=119)),
        "vla": _inst("orch_viola", GmVoice(program=48), volume=34),
        "choir": _inst("vox_choir", GmVoice(program=52), volume=34),
    }
    harmony = Harmony(keys=(0, 2), mode="aeolian", progressions=PROGRESSIONS, n_progressions=2, fixed=True)
    sections = {
        "intro": Section(intensity=0.5, parts=frozenset({"arp"})),
        "rise1": Section(intensity=0.6, parts=frozenset({"viola", "bass", "arp"})),
        "theme": Section(intensity=0.75, parts=frozenset({"cb", "bass", "lead", "viola", "arp"})),
        "rise2": Section(prog=1, intensity=0.85, parts=frozenset({"bass", "horn", "pad", "timp", "viola", "lead", "cb", "arp"})),
        "climax": Section(prog=2, intensity=1.0, parts=frozenset({"bass", "horn", "pad", "timp", "viola", "lead", "cb", "arp"})),
        "resolve": Section(intensity=0.4, parts=frozenset({"arp"})),
    }
    form = ("intro", "rise1", "theme", "theme", "rise2", "climax", "climax", "resolve")
    parts = (
        Part("arp", Arp("piano", register=(12, 27), steps=(0, 2, 4, 6, 8, 10, 12, 14), vol=36, pattern="updown"), pan=100),
        Part("lead", Lead("vln", ScaleRules(leap_probability=0.3, leap_semitones=(3, 4, 5, 7, 8)), LEAD_MOTIFS,
                   vol=48, gate=1.0, vibrato=0x23), pan=84),
        Part("viola", ChordHold("vla", 32), pan=160, min_channels=8),
        Part("bass", BassLine("vc", kind="half", vol=46), pan=176),
        Part("cb", BassHold("cb", 44), pan=150, min_channels=8),
        Part("horn", HornThird("horn", 40), pan=110),
        Part("pad", Pad("choir", vol=34), pan=128),
        Part("timp", Timpani(), pan=128,
             kit=Kit(groups=(("timpani", ("timp", "swell")),), priority={"timp": 2})),
    )
    mod_channels = {6: 1, 8: 2}
