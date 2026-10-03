"""samba（サンバ風）。2/4 の16分格子。系統は seed で選ぶ: ``pagode``（84〜94 BPM。控えめな打楽器）と ``batucada``（100〜112 BPM。打楽器が全員で重なる）。

スルド（1拍目は抑え、2拍目で開いて強く）、タンボリン・アゴゴ・パンデイロの16分、カヴァキーニョの刻み、7弦ギターの低音、7th の和声。
"""
from __future__ import annotations

import random

from ..core.composer import RhythmMotif, ScaleRules
from ..core.model import ChordSpec, GmVoice
from ..core.pitch import CHORD_QUALITIES, fold_into_range
from ..framework.context import Generator, MeasureCtx
from ..framework.gens import Groove, Lead, hits
from ..framework.genre import Genre, Harmony, Kit, Part, Section
from ..framework.plan import Meter, SongPlan, default_plan
from ..framework.registry import register_genre
from ._ornament import OrnamentedLead, inst as _inst

C = ChordSpec

METER = Meter(8, 4, (2, 4))
FAMILIES = {"pagode": ("Pagode (relaxed)", (84, 88, 90, 94)), "batucada": ("Batucada (full percussion)", (100, 104, 108, 112))}
GROOVES = {
    "pagode:main": hits("surdo", (0,), 34) + hits("surdo", (4,), 52) + hits("pandeiro", (0, 2, 4, 6), 30)
                   + hits("pandeiro", (1, 3, 5, 7), 18, 0.8) + hits("shaker", tuple(range(8)), 16, 0.8),
    "batucada:main": hits("surdo", (0,), 36) + hits("surdo", (4,), 58) + hits("tamborim", (0, 3, 4, 6), 38)
                     + hits("agogo_hi", (0, 3, 6), 30) + hits("agogo_lo", (2, 4, 7), 30)
                     + hits("pandeiro", (0, 2, 4, 6), 34) + hits("shaker", tuple(range(8)), 18),
}
LEAD_MOTIFS = {
    "verse": (RhythmMotif(rows=(0, 3, 6)), RhythmMotif(rows=(0, 2, 3, 6)), RhythmMotif(rows=(1, 3, 4, 7))),
    "solo": (RhythmMotif(rows=(0, 1, 3, 4, 6, 7)), RhythmMotif(rows=(0, 2, 3, 4, 6)), RhythmMotif(rows=(0, 3, 4, 6, 7))),
}
PROGRESSIONS = (
    ("iim7-V7-Imaj7-VI7", (C(2, "m7", label="iim7"), C(7, "dom7", label="V7"), C(0, "maj7", label="Imaj7"), C(9, "dom7", label="VI7"))),
    ("Imaj7-II7-iim7-V7", (C(0, "maj7", label="Imaj7"), C(2, "dom7", label="II7"), C(2, "m7", label="iim7"), C(7, "dom7", label="V7"))),
    ("Imaj7-vim7-iim7-V7", (C(0, "maj7", label="Imaj7"), C(9, "m7", label="vim7"), C(2, "m7", label="iim7"), C(7, "dom7", label="V7"))),
)


class Cavaquinho(Generator):
    """カヴァキーニョ／ギターの16分の刻み（和音）。"""

    inst = "cavaco"

    def measure(self, m: MeasureCtx) -> None:
        shape = CHORD_QUALITIES[m.m.quality]
        for step, vol in ((0, 38), (2, 28), (3, 30), (4, 34), (6, 28), (7, 30)):
            m.note(step, "cavaco", m.m.chord.harmony, vel=m.scale_vol(vol), chord=shape, dur=1)


class Violao7(Generator):
    """7弦ギターの低音（拍1に根音、拍2に5度、裏に根音）。"""

    def measure(self, m: MeasureCtx) -> None:
        reg = m.genre.harmony.registers.bass
        root = m.m.chord.bass
        m.note(0, "bass", root, vel=m.scale_vol(52), dur=3)
        m.note(4, "bass", fold_into_range(root + 7, *reg), vel=m.scale_vol(46), dur=2)
        m.note(6, "bass", root, vel=m.scale_vol(38), dur=1)


def _sec(parts, *, prog=0, intensity=0.8, measures=8, motifs="verse") -> Section:
    return Section(prog=prog, measures=measures, intensity=intensity, parts=frozenset(parts), motifs=motifs, meter=METER)


@register_genre
class SambaGenre(Genre):
    id = "samba"
    category = "genre"
    display_name = "Samba"
    description = "サンバ風。2/4 のスルドとタンボリン・アゴゴ・パンデイロの16分、カヴァキーニョの刻み、7thの和声（パゴーヂとバトゥカーダ）"
    description_en = "Samba style: 2/4 surdo with tamborim, agogo and pandeiro sixteenths, cavaquinho strumming, 7th chords (relaxed pagode or full batucada)"
    title = "Samba Carnaval"
    tempo_choices = tuple(sorted({b for f in FAMILIES.values() for b in f[1]}))

    instruments = {
        "surdo": _inst("perc_surdo", GmVoice(drum_note=41)),
        "tamborim": _inst("latin_tamborim", GmVoice(drum_note=75)),
        "agogo_hi": _inst("latin_agogo_hi", GmVoice(drum_note=67)),
        "agogo_lo": _inst("latin_agogo_lo", GmVoice(drum_note=68)),
        "pandeiro": _inst("perc_tambourine", GmVoice(drum_note=54)),
        "shaker": _inst("perc_shaker", GmVoice(drum_note=70)),
        "bass": _inst("bass_finger", GmVoice(program=33), volume=50),
        "cavaco": _inst("gtr_clean_cut", GmVoice(program=24), name="Cavaquinho", volume=38),
        "flute": _inst("wind_flute", GmVoice(program=73), volume=40),
        "gtr": _inst("gtr_nylon", GmVoice(program=24), name="Violao", volume=34),
    }
    harmony = Harmony(keys=(5, 0, 7, 2), mode="ionian", mode_by_quality={"m7": "dorian", "dom7": "mixolydian"},
                      progressions=PROGRESSIONS, n_progressions=2)
    _band = {"drums", "bass", "comp", "lead"}
    sections = {
        "intro": _sec({"drums", "comp", "bass"}, intensity=0.6, measures=4),
        "a": _sec(_band, intensity=0.8),
        "b": _sec(_band | {"gtr"}, prog=1, intensity=0.95),
        "solo": _sec(_band | {"gtr"}, intensity=1.0, motifs="solo"),
        "outro": _sec({"drums", "comp", "bass"}, intensity=0.6, measures=4),
    }
    form = ("intro", "a", "a", "b", "b", "solo", "a", "outro")
    parts = (
        Part("drums", Groove(GROOVES, groove_name=lambda sp: f"{sp.extra['family']}:{sp.section.groove}"), pan=128,
             kit=Kit(groups=(("surdo", ("surdo",)), ("tamborim/agogo", ("tamborim", "agogo_hi", "agogo_lo")),
                             ("pandeiro/shaker", ("pandeiro", "shaker"))),
                     priority={"tamborim": 3, "agogo_hi": 2, "agogo_lo": 2, "pandeiro": 2},
                     single_priority={"surdo": 4, "tamborim": 3, "agogo_hi": 2, "agogo_lo": 2, "pandeiro": 2, "shaker": 1},
                     group_pan={"tamborim/agogo": 96, "pandeiro/shaker": 164})),
        Part("bass", Violao7(), pan=128),
        Part("comp", Cavaquinho(), pan=84),
        Part("lead", OrnamentedLead("flute", ScaleRules(leap_probability=0.15, leap_semitones=(3, 4, 5)), LEAD_MOTIFS,
                                    vol=40, gate=0.8, grace=0.25), pan=172),
        Part("gtr", Lead("gtr", ScaleRules(leap_probability=0.1), LEAD_MOTIFS, vol=32, gate=0.7), pan=100, min_channels=6),
    )
    mod_channels = {4: 1, 6: 2, 8: 1}

    def plan(self, rng: random.Random) -> SongPlan:
        family = rng.choice(list(FAMILIES))
        base = default_plan(self, rng)
        label, bpms = FAMILIES[family]
        base.bpm = rng.choice(bpms)
        base.summary = [f"Rhythm      : {label}", *base.summary]
        base.extra = dict(base.extra, family=family)
        for sp in base.sections.values():
            sp.extra = dict(sp.extra, family=family)
        return base
