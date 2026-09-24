"""warm: 温かいアコースティック（DESIGN.md §6.16.7）。B4（4ch、Amiga 互換）: カホンとシェイカー、ベース、
アコースティックギターのストローク、ピアノの旋律。"""
from __future__ import annotations

from ..core.composer import RhythmMotif, ScaleRules
from ..core.model import ChordSpec
from ..profiles.band_common import BandProfile, BassSpec, ChannelDef, CompSpec, LeadSpec, Section, hits, preset
from ..profiles.registry import register_profile

C = ChordSpec
CH_PERC, CH_BASS, CH_GTR, CH_LEAD = range(4)

CAJON = hits("low", (0, 8, 10), 50) + hits("slap", (4, 12), 46) + hits("shaker", (2, 6, 14), 22, 0.8)
LEAD_MOTIFS = {
    "verse": (RhythmMotif((0, 4, 8, 12)), RhythmMotif((0, 2, 4, 8)), RhythmMotif((0, 4, 6, 8, 12))),
}
BAND = frozenset({"drums", "bass", "comp"})


@register_profile
class WarmProfile(BandProfile):
    id = "warm"
    category = "mood"
    display_name = "Warm"
    description = "温かい。アコースティックギターとピアノ、長調の穏やかな伴奏"
    description_en = "Warm: acoustic guitar and piano in a gentle major key"
    title = "Warm Spring Day"
    default_filename = "Warm.mod"
    tempo_choices = (88, 92, 96, 100)

    KIT = (
        ("low", preset("perc_cajon")), ("slap", preset("perc_cajon_slap")), ("shaker", preset("perc_shaker")),
        ("bass", preset("bass_finger")), ("piano", preset("keys_piano")),
    )
    CHORD_KITS = {"gtr": (preset("gtr_acoustic"), 12.0)}
    CHANNELS = (
        ChannelDef("cajon/shaker", ("low", "slap", "shaker"), (("slap", 3), ("low", 2))),
        ChannelDef("bass", ("bass",)),
        ChannelDef("guitar", ("gtr",)),
        ChannelDef("piano", ("piano",)),
    )
    DRUM_CHANNEL = {"low": CH_PERC, "slap": CH_PERC, "shaker": CH_PERC}
    KEYS = (7, 2, 0)
    PROGRESSIONS = (
        ("I-V-vi-IV", (C(0, "maj", label="I"), C(7, "maj", label="V"), C(9, "min", label="vi"), C(5, "maj", label="IV"))),
        ("I-IV-ii-V", (C(0, "maj", label="I"), C(5, "maj", label="IV"), C(2, "min", label="ii"), C(7, "maj", label="V"))),
        ("I-vi-IV-V", (C(0, "maj", label="I"), C(9, "min", label="vi"), C(5, "maj", label="IV"), C(7, "maj", label="V"))),
    )
    SECTIONS = {
        "intro": Section("intro", prog=0, intensity=0.5, parts=frozenset({"comp", "bass"})),
        "a": Section("a", prog=0, intensity=0.7, parts=BAND | {"lead"}),
        "b": Section("b", prog=1, intensity=0.85, parts=BAND | {"lead"}),
        "outro": Section("outro", prog=0, intensity=0.5, parts=frozenset({"comp", "bass"})),
    }
    FORM = ("intro", "a", "b", "a", "b", "outro")
    GROOVES = {"main": CAJON}
    BASS = BassSpec("bass", CH_BASS, kind="rootfifth", vol=50)
    COMP = CompSpec("gtr", CH_GTR, kind="strum", vol=40)
    LEAD = LeadSpec("piano", CH_LEAD, ScaleRules(leap_probability=0.15, leap_semitones=(3, 4, 5)), LEAD_MOTIFS,
                    vol=46, gate=1.0)
