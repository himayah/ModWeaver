"""mood-kayo（ムード歌謡風。NEW_GENRES_DESIGN.md §10）。

系統は seed で選ぶ: ``rumba``（ゆったり）と ``chacha``（8分・クラーベ寄りの刻み）。テナーサックスのしゃくり、
ハワイアンギターの間奏、ストリングス、7th を多用する短調の和声、最後のサビは半音上げ。ボーカルは含まない。
"""
from __future__ import annotations

import random

from ..core.composer import RhythmMotif, ScaleRules
from ..core.model import ChordSpec, GmVoice
from ..core.pitch import CHORD_QUALITIES, fold_into_range
from ..framework.context import Generator, MeasureCtx
from ..framework.gens import Groove, Layer, Pad, Sing, hits
from ..framework.genre import Genre, Harmony, Kit, Part, Section, Voice
from ..framework.plan import SongPlan, default_plan
from ..framework.registry import register_genre
from ._ornament import OrnamentedLead, WithTempo, inst as _inst

C = ChordSpec

FAMILIES = {                                   # 名前: (表示, テンポの候補)
    "rumba": ("Rumba", (92, 96, 100, 104, 108)),
    "chacha": ("Cha-cha-cha", (112, 116, 120, 124)),
}
GROOVES = {
    "rumba:main": hits("kick", (0, 10), 46) + hits("clave", (0, 3, 6, 10, 12), 30)
                  + hits("bongo", (7, 14), 30, 0.8) + hits("shaker", (0, 2, 4, 6, 8, 10, 12, 14), 16, 0.9),
    "chacha:main": hits("kick", (0, 8), 46) + hits("rim", (0, 4, 8, 10, 12), 34) + hits("bongo", (2, 6, 14), 28, 0.8)
                   + hits("shaker", tuple(range(0, 16, 2)), 16, 0.9),
}
COMP = {"rumba": ((0, 40), (6, 30), (10, 34)),
        "chacha": ((0, 40), (4, 28), (8, 34), (12, 28), (14, 24))}
BASS = {"rumba": ((0, "r", 52), (6, "f", 42), (10, "r", 46)),
        "chacha": ((0, "r", 52), (4, "f", 40), (8, "r", 46), (12, "f", 40))}
LEAD_MOTIFS = {
    "verse": (RhythmMotif(rows=(0, 6, 8, 12)), RhythmMotif(rows=(0, 4, 8)), RhythmMotif(rows=(2, 6, 10, 12))),
    "solo": (RhythmMotif(rows=(0, 3, 6, 8, 12)), RhythmMotif(rows=(0, 4, 6, 10, 12)), RhythmMotif(rows=(0, 8))),
}
PROGRESSIONS = (
    ("im7-VImaj7-iim7b5-V7", (C(0, "m7", label="im7"), C(8, "maj7", label="VImaj7"), C(2, "m7b5", label="iim7b5"),
                              C(7, "dom7", label="V7"))),
    ("im7-ivm7-V7-im7", (C(0, "m7", label="im7"), C(5, "m7", label="ivm7"), C(7, "dom7", label="V7"), C(0, "m7", label="im7"))),
    ("im7-ivm7-bVII7-bIIImaj7", (C(0, "m7", label="im7"), C(5, "m7", label="ivm7"), C(10, "dom7", label="bVII7"),
                                 C(3, "maj7", label="bIIImaj7"))),
    ("im7-dim7-iim7b5-V7", (C(0, "m7", label="im7"), C(1, "dim7", label="#idim7"), C(2, "m7b5", label="iim7b5"),
                            C(7, "dom7", label="V7"))),
)


class KayoComp(Generator):
    def measure(self, m: MeasureCtx) -> None:
        for step, vol in COMP[m.song.extra["family"]]:
            m.note(step, "ep", m.m.chord.harmony, vel=m.scale_vol(vol), chord=CHORD_QUALITIES[m.m.quality], strum_ms=6.0)


class KayoBass(Generator):
    def measure(self, m: MeasureCtx) -> None:
        reg = m.genre.harmony.registers.bass
        for step, what, vol in BASS[m.song.extra["family"]]:
            note = m.m.chord.bass if what == "r" else fold_into_range(m.m.chord.bass + 7, *reg)
            m.note(step, "bass", note, vel=m.scale_vol(vol))


def _sec(parts, *, prog=0, intensity=0.8, measures=8, motifs="verse", key_offset=0) -> Section:
    return Section(prog=prog, measures=measures, intensity=intensity, parts=frozenset(parts), motifs=motifs,
                   key_offset=key_offset)


@register_genre
class MoodKayoGenre(Genre):
    id = "mood-kayo"
    category = "style"
    display_name = "Mood Kayo"
    description = "ムード歌謡風。テナーサックスのしゃくり、ハワイアンギターの間奏、ストリングス、ルンバ／チャチャチャと7thの和声（歌は含まない）"
    description_en = "Mood kayo style: scooping tenor sax, Hawaiian steel guitar, strings, rumba or cha-cha-cha and 7th chords (a sung part with --voice)"
    title = "Mood Kayo Night"
    tempo_choices = tuple(sorted({b for f in FAMILIES.values() for b in f[1]}))

    instruments = {
        "kick": _inst("drum_pop_kick", GmVoice(drum_note=36)),
        "rim": _inst("drum_rim", GmVoice(drum_note=37)),
        "clave": _inst("perc_clave", GmVoice(drum_note=75)),
        "bongo": _inst("mood_bongo", GmVoice(drum_note=60)),
        "shaker": _inst("perc_shaker", GmVoice(drum_note=70)),
        "bass": _inst("bass_finger", GmVoice(program=33)),
        "ep": _inst("keys_ep", GmVoice(program=4), volume=34),
        "sax": _inst("swing_sax_lead", GmVoice(program=66), volume=44),
        "steel": _inst("mood_steel_gtr", GmVoice(program=26)),
        "strings": _inst("orch_violin", GmVoice(program=48), name="Strings", volume=30),
        "vibes": _inst("min_vibraphone", GmVoice(program=11), volume=26),
        "voice": Voice(GmVoice(program=54), timbre="female", volume=46),     # --voice で歌う（旋律は lead と同じ）
    }
    harmony = Harmony(keys=(9, 2, 4, 0), mode="aeolian", progressions=PROGRESSIONS, n_progressions=2)
    _core = {"drums", "bass", "comp"}
    sections = {
        "intro": _sec({"lead", "comp", "bass"}, intensity=0.5, measures=4),
        "verse": _sec(_core | {"lead", "strings", "vocal"}, intensity=0.7),
        "chorus": _sec(_core | {"lead", "strings", "vibes", "vocal"}, prog=1, intensity=0.9),
        "interlude": _sec(_core | {"steel", "strings", "vibes"}, intensity=0.8, motifs="solo"),
        "chorus2": _sec(_core | {"lead", "strings", "vibes", "vocal"}, prog=1, intensity=1.0, key_offset=1),
        "outro": _sec({"lead", "comp", "bass", "strings"}, intensity=0.5, measures=4),
    }
    form = ("intro", "verse", "chorus", "interlude", "verse", "chorus2", "outro")
    parts = (
        Part("drums", WithTempo(Groove(GROOVES, groove_name=lambda sp: f"{sp.extra['family']}:{sp.section.groove}"),
                                lambda sp: (1.0, 0.88) if sp.name == "outro" else None), pan=128,
             kit=Kit(groups=(("kick/rim", ("kick", "rim")), ("percussion", ("clave", "bongo", "shaker"))),
                     priority={"kick": 3, "rim": 2}, single_priority={"kick": 3, "rim": 2, "clave": 1, "bongo": 1, "shaker": 1},
                     group_pan={"percussion": 168})),
        Part("bass", KayoBass(), pan=128),
        Part("comp", KayoComp(), pan=84),
        Part("lead", OrnamentedLead("sax", ScaleRules(leap_probability=0.15, leap_semitones=(3, 4, 5)), LEAD_MOTIFS,
                                    vol=46, gate=0.95, vibrato=0x34, scoop=0.4, kobushi=0.3, scoop_semitones=1.0),
             pan=172),
        Part("steel", OrnamentedLead("steel", ScaleRules(leap_probability=0.1, leap_semitones=(3, 4, 5)), LEAD_MOTIFS,
                                     vol=40, gate=1.0, vibrato=0x24, scoop=0.6, scoop_semitones=2.0),
             pan=100, min_channels=6),
        Part("strings", Pad("strings", vol=26), pan=128, min_channels=6),
        Part("vibes", Layer("vibes", vol=24, register=(19, 31)), follow="comp", pan=70, min_channels=8),
        Part("vocal", Sing("voice"), pan=128, depends=("lead",), min_channels=6, requires=frozenset({"voice"})),
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
