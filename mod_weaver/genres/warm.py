"""warm（旧 genres/warm.py の宣言を機械変換したもの。DESIGN.md §6）。"""
from __future__ import annotations

from ..core.composer import RhythmMotif, ScaleRules
from ..core.model import ChordSpec, GmVoice
from ..core.synth_presets import PRESETS
from ..framework.gens import BassLine, Comp, Groove, Layer, Lead, hits
from ..framework.genre import Genre, Harmony, Instrument, Kit, Part, Section
from ..framework.registry import register_genre

C = ChordSpec


def _inst(key: str, gm: GmVoice, **changes) -> Instrument:
    patch = PRESETS[key]
    if changes:
        import dataclasses
        patch = dataclasses.replace(patch, **changes)
    return Instrument(patch=patch, gm=gm)

GROOVES = {
    "main": hits("low", (0, 8, 10), 50) + hits("slap", (4, 12), 46) + hits("shaker", (2, 6, 14), 22, 0.8),
}
LEAD_MOTIFS = {
    "verse": (RhythmMotif(rows=(0, 4, 8, 12)), RhythmMotif(rows=(0, 2, 4, 8)), RhythmMotif(rows=(0, 4, 6, 8, 12))),
}
PROGRESSIONS = (
    ("I-V-vi-IV", (C(0, "maj", label="I"), C(7, "maj", label="V"), C(9, "min", label="vi"), C(5, "maj", label="IV"))),
    ("I-IV-ii-V", (C(0, "maj", label="I"), C(5, "maj", label="IV"), C(2, "min", label="ii"), C(7, "maj", label="V"))),
    ("I-vi-IV-V", (C(0, "maj", label="I"), C(9, "min", label="vi"), C(5, "maj", label="IV"), C(7, "maj", label="V"))),
)


@register_genre
class WarmGenre(Genre):
    id = "warm"
    category = "mood"
    display_name = "Warm"
    description = "温かい。アコースティックギターとピアノ、長調の穏やかな伴奏"
    description_en = "Warm: acoustic guitar and piano in a gentle major key"
    title = "Warm Spring Day"
    tempo_choices = (88, 92, 96, 100)

    instruments = {
        "low": _inst("perc_cajon", GmVoice(drum_note=36)),
        "slap": _inst("perc_cajon_slap", GmVoice(drum_note=38)),
        "shaker": _inst("perc_shaker", GmVoice(drum_note=70)),
        "bass": _inst("bass_finger", GmVoice(program=33)),
        "piano": _inst("keys_piano", GmVoice(program=0)),
        "flute": _inst("wind_flute", GmVoice(program=73), volume=30),
        "gtr": _inst("gtr_acoustic", GmVoice(program=25)),
    }
    harmony = Harmony(keys=(7, 2, 0), mode="ionian", progressions=PROGRESSIONS, n_progressions=2)
    sections = {
        "intro": Section(intensity=0.5, parts=frozenset({"comp", "bass"})),
        "a": Section(intensity=0.7, parts=frozenset({"comp", "bass", "drums", "lead"})),
        "b": Section(prog=1, intensity=0.85, parts=frozenset({"comp", "bass", "drums", "lead"})),
        "outro": Section(intensity=0.5, parts=frozenset({"comp", "bass"})),
    }
    form = ("intro", "a", "b", "a", "b", "outro")
    parts = (
        Part("drums", Groove(GROOVES), pan=128,
             kit=Kit(groups=(("cajon", ("low", "slap")), ("shaker", ("shaker",))),
                     priority={"slap": 3, "low": 2},
                     single_priority={"low": 2, "slap": 3, "shaker": 1},
                     group_pan={"shaker": 164})),
        Part("bass", BassLine("bass", kind="rootfifth", vol=50), pan=128),
        Part("comp", Comp("gtr", kind="strum", vol=40, strum_ms=12.0), pan=84),
        Part("lead", Lead("piano", ScaleRules(leap_probability=0.15, leap_semitones=(3, 4, 5)), LEAD_MOTIFS,
                   vol=46, gate=1.0), pan=172),
        Part("flute", Layer("flute", vol=26, register=(19, 31)), follow="lead", pan=100, min_channels=6),
    )
    mod_channels = {4: 2, 6: 1}
