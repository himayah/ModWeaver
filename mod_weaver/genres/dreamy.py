"""dreamy: 夢見心地のアルペジオ（DESIGN.md §6.16.5）。E6（6ch）: エコーのかかったアルペジオと厚いパッド、ハーフタイムのビート。"""
from __future__ import annotations

from ..core.composer import RhythmMotif, ScaleRules
from ..core.model import ChordSpec
from ..profiles.band_common import (
    ArpSpec, BandProfile, BassSpec, ChannelDef, EchoSpec, Fold, LayerSpec, LeadSpec, PadSpec, Section, hits, keep,
    preset,
)
from ..profiles.registry import register_profile

C = ChordSpec
CH_KS, CH_BASS, CH_PAD, CH_ARP, CH_ECHO, CH_LEAD, CH_X_FLUTE_ECHO, CH_X_VOICE = range(8)   # 7・8 番目は 8ch の編成だけ

HALF = hits("kick", (0, 10), 44) + hits("rim", (8,), 34)
LEAD_MOTIFS = {"verse": (RhythmMotif((0, 8)), RhythmMotif((0, 6, 12)), RhythmMotif((4, 12)))}


@register_profile
class DreamyProfile(BandProfile):
    id = "dreamy"
    category = "mood"
    display_name = "Dreamy"
    description = "夢見心地。深い残響感のアルペジオとパッド"
    description_en = "Dreamy: echoing arpeggios over lush pads"
    title = "Dreamy Haze"
    default_filename = "Dreamy.mod"
    tempo_choices = (80, 84, 88, 92)

    KIT = (
        ("kick", preset("drum_pop_kick", volume=44)), ("rim", preset("drum_rim")), ("bass", preset("fb_sub")),
        ("arp", preset("syn_arp_bell")), ("lead", preset("wind_flute", volume=36)),
        ("voice", preset("vox_ooh", volume=30)),
    )
    CHORD_KITS = {"pad": (preset("pad_glass"), 0.0)}
    CHANNELS = (
        ChannelDef("kick/rim", ("kick", "rim"), (("rim", 2),), pan=128),
        ChannelDef("sub", ("bass",), pan=128),
        ChannelDef("pad", ("pad",), pan=72),
        ChannelDef("arp", ("arp",), pan=176),
        ChannelDef("arp echo", ("arp",), pan=80),
        ChannelDef("flute", ("lead",), pan=150),
        ChannelDef("flute echo", ("lead",), pan=96),
        ChannelDef("voice", ("voice",), pan=160),
    )
    DRUM_CHANNEL = {"kick": CH_KS, "rim": CH_KS}
    KEYS = (3, 8, 1)
    MODE = "lydian"
    PROGRESSIONS = (
        ("Imaj7-IVmaj7", (C(0, "maj7", label="Imaj7"), C(5, "maj7", label="IVmaj7"))),
        ("I-iii-IV-iv", (C(0, "add9", label="Iadd9"), C(4, "m7", label="iii7"), C(5, "maj7", label="IVmaj7"),
                         C(5, "m6", label="ivm6"))),
    )
    SECTIONS = {
        "intro": Section("intro", prog=0, intensity=0.5, parts=frozenset({"pad", "arp"})),
        "a": Section("a", prog=0, intensity=0.7, parts=frozenset({"drums", "bass", "pad", "arp", "lead"})),
        "b": Section("b", prog=1, intensity=0.8, parts=frozenset({"drums", "bass", "pad", "arp", "lead"})),
        "outro": Section("outro", prog=0, intensity=0.4, parts=frozenset({"pad", "arp"})),
    }
    FORM = ("intro", "a", "b", "a", "b", "outro")
    GROOVES = {"main": HALF}
    BASS = BassSpec("bass", CH_BASS, kind="whole", vol=50)
    PAD = PadSpec("pad", CH_PAD, vol=32)
    ARP = ArpSpec("arp", CH_ARP, rows=tuple(range(16)), vol=30, pattern="updown")
    LEAD = LeadSpec("lead", CH_LEAD, ScaleRules(leap_probability=0.3, leap_semitones=(4, 5, 7)), LEAD_MOTIFS,
                    vol=36, gate=0.95, vibrato=0x32)
    ECHO = (EchoSpec(CH_ARP, CH_ECHO, delay=3, ratio=0.5, repeats=2),
            EchoSpec(CH_LEAD, CH_X_FLUTE_ECHO, delay=3, ratio=0.45, offs=True))
    LAYERS = (LayerSpec("voice", CH_X_VOICE, follow="lead", vol=24, register=(19, 31)),)
    ARRANGEMENTS = {                          # DESIGN.md §6.14: 4ch＝小編成、6ch＝標準、8ch＝任意パートを足す
        4: keep("kick/rim", "sub", "pad", "arp"),
        6: keep("kick/rim", "sub", "pad", "arp", "arp echo", "flute"),
        8: keep("kick/rim", "sub", "pad", "arp", "arp echo", "flute", "flute echo", "voice"),
    }
