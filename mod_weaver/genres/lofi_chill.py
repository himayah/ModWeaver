"""lofi-chill: ローファイ・プロデューサー風のチル（DESIGN.md §6.16.30）。B6（6ch）: ギターとフルート、サイドチェインのうねり、雨音。"""
from __future__ import annotations

from ..core import groove
from ..core.composer import RhythmMotif, ScaleRules
from ..core.model import ChordSpec
from ..profiles.band_common import (
    BandProfile, BassSpec, ChannelDef, CompSpec, FxSpec, LeadSpec, Section, hits, preset,
)
from ..profiles.registry import register_profile

C = ChordSpec
CH_KS, CH_HAT, CH_BASS, CH_GTR, CH_LEAD, CH_FX = range(6)

CHILL = (hits("kick", (0, 10), 58) + hits("rim", (4, 12), 40)
         + hits("shaker", range(0, 16, 2), 20) + hits("kick", (7,), 40, 0.4))

LEAD_MOTIFS = {
    "verse": (RhythmMotif((0, 4, 6, 12)), RhythmMotif((2, 6, 8, 12)), RhythmMotif((0, 3, 8, 10))),
}
BEAT = frozenset({"drums", "bass", "comp", "fx"})


@register_profile
class LofiChillProfile(BandProfile):
    id = "lofi-chill"
    category = "style"
    display_name = "Lo-fi Chill"
    description = "ローファイ・チル。柔らかいギターとフルート、うねるサイドチェインと雨音"
    description_en = "Lo-fi chill: soft guitar and flute, pumping sidechain and rain ambience"
    title = "Lo-fi Chill Rain"
    default_filename = "LofiChill.mod"
    tempo_choices = (72, 76, 80, 84, 88)

    KIT = (
        ("kick", preset("drum_boombap_kick")), ("rim", preset("drum_rim")), ("shaker", preset("perc_shaker")),
        ("bass", preset("bass_finger")), ("lead", preset("wind_flute", volume=36)), ("rain", preset("fx_rain")),
    )
    CHORD_KITS = {"gtr": (preset("gtr_nylon"), 18.0)}
    CHANNELS = (
        ChannelDef("kick/rim", ("kick", "rim"), (("rim", 2),), pan=128),
        ChannelDef("shaker", ("shaker",), pan=164),
        ChannelDef("bass", ("bass",), pan=128),
        ChannelDef("guitar", ("gtr",), pan=84),
        ChannelDef("flute", ("lead",), pan=172),
        ChannelDef("rain", ("rain",), pan=128),
    )
    DRUM_CHANNEL = {"kick": CH_KS, "rim": CH_KS, "shaker": CH_HAT}
    KEYS = (0, 5, 7, 10)
    PROGRESSIONS = (
        ("Imaj7-iii7-vi7-IVmaj7", (C(0, "maj7", label="Imaj7"), C(4, "m7", label="iii7"), C(9, "m7", label="vi7"),
                                   C(5, "maj7", label="IVmaj7"))),
        ("IVmaj7-ivm7-Imaj7-vi7", (C(5, "maj7", label="IVmaj7"), C(5, "m7", label="ivm7"), C(0, "maj7", label="Imaj7"),
                                   C(9, "m7", label="vi7"))),
        ("Imaj9-IVmaj9", (C(0, "maj9", label="Imaj9"), C(5, "maj9", label="IVmaj9"))),
    )
    SECTIONS = {
        "intro": Section("intro", prog=0, intensity=0.4, parts=frozenset({"comp", "fx"})),
        "a": Section("a", prog=0, intensity=0.7, parts=BEAT | {"lead"}),
        "b": Section("b", prog=1, intensity=0.7, parts=BEAT | {"lead"}),
        "outro": Section("outro", prog=0, intensity=0.4, parts=frozenset({"comp", "fx"})),
    }
    FORM = ("intro", "a", "a", "b", "a", "outro")
    GROOVES = {"main": CHILL}
    SWING = groove.SwingConfig(long_speed=7, short_speed=5)
    SIDECHAIN = (("kick", CH_GTR, 0.45, 3), ("kick", CH_FX, 0.5, 3))   # kick でギターと雨音をうねらせる
    BASS = BassSpec("bass", CH_BASS, kind="half", vol=54)
    COMP = CompSpec("gtr", CH_GTR, kind="half", vol=44)
    FX = FxSpec("rain", CH_FX, every=2, vol=26)
    LEAD = LeadSpec("lead", CH_LEAD, ScaleRules(leap_probability=0.2, leap_semitones=(3, 4, 5, 7)), LEAD_MOTIFS,
                    vol=40, gate=0.9, vibrato=0x32)
