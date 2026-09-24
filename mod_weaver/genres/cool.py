"""cool: 涼しげな透明感（DESIGN.md §12.7.8）。E6（6ch）: 透明感のあるシンセと軽い2ステップのビート。"""
from __future__ import annotations

from ..core.composer import RhythmMotif, ScaleRules
from ..core.model import ChordSpec
from ..profiles.band_common import (
    BandProfile, BassSpec, ChannelDef, EchoSpec, LeadSpec, PadSpec, Section, hits, preset,
)
from ..profiles.registry import register_profile

C = ChordSpec
CH_KS, CH_HAT, CH_BASS, CH_PAD, CH_LEAD, CH_ECHO = range(6)

TWO_STEP = (hits("kick", (0, 10), 56) + hits("snare", (4, 12), 42)
            + hits("hat", (2, 6, 10, 14), 26) + hits("rim", (7, 13), 22, 0.6))
LEAD_MOTIFS = {"verse": (RhythmMotif((0, 3, 6)), RhythmMotif((0, 2, 8, 10)), RhythmMotif((4, 7, 12)))}
BASE = frozenset({"drums", "bass", "pad"})


@register_profile
class CoolProfile(BandProfile):
    id = "cool"
    category = "mood"
    display_name = "Cool"
    description = "涼しげ。透明感のあるシンセと軽い2ステップのビート"
    description_en = "Cool: glassy synths over a light two-step beat"
    title = "Cool Night Air"
    default_filename = "Cool.mod"
    tempo_choices = (100, 104, 108, 112)

    KIT = (
        ("kick", preset("drum_pop_kick")), ("snare", preset("drum_rim", volume=40)), ("hat", preset("drum_909_hat")),
        ("rim", preset("perc_clave")), ("bass", preset("fb_sub")), ("lead", preset("syn_pluck")),
    )
    CHORD_KITS = {"pad": (preset("pad_glass"), 0.0)}
    CHANNELS = (
        ChannelDef("kick/snare", ("kick", "snare"), (("snare", 2),), pan=128),
        ChannelDef("hat", ("hat", "rim"), (("rim", 2),), pan=164),
        ChannelDef("sub", ("bass",), pan=128),
        ChannelDef("glass pad", ("pad",), pan=84),
        ChannelDef("pluck", ("lead",), pan=150),
        ChannelDef("echo", ("lead",), pan=100),
    )
    DRUM_CHANNEL = {"kick": CH_KS, "snare": CH_KS, "hat": CH_HAT, "rim": CH_HAT}
    KEYS = (6, 11, 1)
    MODE = "dorian"
    PROGRESSIONS = (
        ("i9-IV9", (C(0, "m9", label="i9"), C(5, "dom9", label="IV9"))),
        ("i7-bVIImaj7-bVImaj7-v7", (C(0, "m7", label="i7"), C(10, "maj7", label="bVIImaj7"),
                                    C(8, "maj7", label="bVImaj7"), C(7, "m7", label="v7"))),
    )
    SECTIONS = {
        "intro": Section("intro", prog=0, intensity=0.5, parts=frozenset({"pad", "lead"})),
        "a": Section("a", prog=0, intensity=0.8, parts=BASE | {"lead"}),
        "b": Section("b", prog=1, intensity=0.9, parts=BASE | {"lead"}),
        "break": Section("break", prog=1, intensity=0.5, parts=frozenset({"pad", "bass"})),
        "outro": Section("outro", prog=0, intensity=0.5, parts=frozenset({"pad", "lead"})),
    }
    FORM = ("intro", "a", "b", "break", "a", "b", "outro")
    GROOVES = {"main": TWO_STEP}
    BASS = BassSpec("bass", CH_BASS, kind="half", vol=54)
    PAD = PadSpec("pad", CH_PAD, vol=30)
    ARP_REGISTER = (24, 35)
    LEAD = LeadSpec("lead", CH_LEAD, ScaleRules(leap_probability=0.3, leap_semitones=(3, 5, 7)), LEAD_MOTIFS,
                    vol=42, gate=0.6)
    ECHO = (EchoSpec(CH_LEAD, CH_ECHO, delay=3, ratio=0.5, repeats=2),)
