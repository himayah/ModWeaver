"""fado（ファド風。NEW_GENRES_DESIGN.md §14.5）。

ポルトガルギター風の装飾的な旋律（前打音・ロール）、ヴィオラ（ガット）のアルペジオ、ベース、ストリングス、
歌の代わりのヴァイオリンの異種同音。ゆっくりした短調で、間奏は「ギターラーダ」。終わりは減速。ボーカルは含まない。
"""
from __future__ import annotations

from ..core.composer import RhythmMotif, ScaleRules
from ..core.model import ChordSpec, GmVoice
from ..framework.gens import BassLine, Comp, Pad
from ..framework.genre import Genre, Harmony, Part, Section
from ..framework.registry import register_genre
from ._ornament import Heterophony, OrnamentedLead, WithTempo, inst as _inst

C = ChordSpec

LEAD_MOTIFS = {
    "verse": (RhythmMotif(rows=(0, 4, 6, 8, 12)), RhythmMotif(rows=(0, 3, 4, 8, 10, 12)), RhythmMotif(rows=(0, 6, 8))),
    "solo": (RhythmMotif(rows=(0, 2, 4, 6, 8, 10, 12, 14)), RhythmMotif(rows=(0, 2, 3, 4, 6, 8, 12)), RhythmMotif(rows=(0, 4, 6, 8, 10, 12))),
}
PROGRESSIONS = (
    ("i-iv-V7-i", (C(0, "min", label="i"), C(5, "min", label="iv"), C(7, "dom7", label="V7"), C(0, "min", label="i"))),
    ("i-VI-iv-V7", (C(0, "min", label="i"), C(8, "maj", label="VI"), C(5, "min", label="iv"), C(7, "dom7", label="V7"))),
    ("i-V7-i-iv", (C(0, "min", label="i"), C(7, "dom7", label="V7"), C(0, "min", label="i"), C(5, "min", label="iv"))),
)


def _sec(parts, *, prog=0, intensity=0.7, measures=8, motifs="verse") -> Section:
    return Section(prog=prog, measures=measures, intensity=intensity, parts=frozenset(parts), motifs=motifs)


@register_genre
class FadoGenre(Genre):
    id = "fado"
    category = "genre"
    display_name = "Fado"
    description = "ファド風。ポルトガルギター風の装飾的な旋律、ガットギターのアルペジオ、ゆっくりした短調、ギターラーダの間奏（歌は含まない）"
    description_en = "Fado style: ornamented Portuguese-guitar-like melody, nylon arpeggios, slow minor key, a guitarrada interlude (no vocals)"
    title = "Fado Saudade"
    tempo_choices = (72, 76, 80, 84, 88, 94, 100)

    instruments = {
        "bass": _inst("bass_finger", GmVoice(program=33), volume=46),
        "viola": _inst("gtr_nylon", GmVoice(program=24), volume=38),
        "guitarra": _inst("gtr_clean_arp", GmVoice(program=25), name="Guitarra", volume=42),
        "violin": _inst("orch_violin", GmVoice(program=40), name="Fiddle", volume=34),
        "strings": _inst("orch_violin", GmVoice(program=48), name="Strings", volume=26),
    }
    harmony = Harmony(keys=(9, 2, 4, 7), mode="aeolian", progressions=PROGRESSIONS, n_progressions=2)
    _band = {"bass", "comp", "lead"}
    sections = {
        "intro": _sec({"comp", "lead"}, intensity=0.5, measures=4),
        "verse": _sec(_band | {"strings"}, intensity=0.65),
        "chorus": _sec(_band | {"strings"}, prog=1, intensity=0.85),
        "guitarrada": _sec(_band, intensity=0.8, motifs="solo"),
        "outro": _sec({"comp", "lead", "bass"}, intensity=0.5, measures=4),
    }
    form = ("intro", "verse", "chorus", "verse", "guitarrada", "chorus", "outro")
    parts = (
        Part("bass", BassLine("bass", kind="rootfifth", vol=46), pan=128),
        Part("comp", Comp("viola", kind="fingerpick", vol=36, chordal=False), pan=84),
        Part("lead", WithTempo(OrnamentedLead("guitarra", ScaleRules(leap_probability=0.12, leap_semitones=(3, 4, 5)),
                                              LEAD_MOTIFS, vol=44, gate=0.9, grace=0.4, roll=0.25),
                               lambda sp: (1.0, 0.85) if sp.name == "outro" else (1.0, 1.0)), pan=172),
        Part("strings", Pad("strings", vol=26), pan=128),
        Part("violin", Heterophony("violin", delay=2, drop=0.3, shift=0, vol_ratio=0.7, lo=12, hi=35, min_dur=2),
             follow="lead", pan=100, min_channels=6),
    )
    mod_channels = {4: 1, 6: 2}
