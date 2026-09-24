"""synthwave: シンセウェイブ（DESIGN.md §6.16.24）。E6（6ch）: 80年代のシンセ、ゲートスネア、8分で脈打つベース。"""
from __future__ import annotations

from ..core.composer import RhythmMotif, ScaleRules
from ..core.model import ChordSpec
from ..profiles.band_common import (
    ArpSpec, BandProfile, BassSpec, ChannelDef, LeadSpec, PadSpec, Section, hits, preset,
)
from ..profiles.registry import register_profile

C = ChordSpec
CH_KS, CH_HAT, CH_BASS, CH_PAD, CH_LEAD, CH_ARP = range(6)

MAIN = hits("kick", (0, 8), 60) + hits("snare", (4, 12), 54) + hits("hat", range(16), 20, 0.85)
LEAD_MOTIFS = {
    "verse": (RhythmMotif((0, 4, 6, 8, 12)), RhythmMotif((0, 6, 8, 10, 12))),
    "solo": (RhythmMotif((0, 2, 4, 6, 8, 10, 12, 14)), RhythmMotif((0, 3, 4, 6, 8, 11, 12))),
}
BASE = frozenset({"drums", "bass", "pad", "arp"})


@register_profile
class SynthwaveProfile(BandProfile):
    id = "synthwave"
    display_name = "Synthwave / Retrowave"
    description = "シンセウェイブ。80年代のシンセとゲートスネア、8分で脈打つベース"
    description_en = "Synthwave: 80s synths, gated snare and a pulsing eighth-note bass"
    title = "Synthwave Drive"
    default_filename = "Synthwave.mod"
    tempo_choices = (96, 100, 104, 108, 112)

    KIT = (
        ("kick", preset("drum_pop_kick")), ("snare", preset("drum_gated_snare")), ("hat", preset("nostalgic_hihat")),
        ("bass", preset("bass_synth_saw")), ("lead", preset("syn_saw_lead")), ("arp", preset("syn_arp_bell")),
    )
    CHORD_KITS = {"pad": (preset("syn_poly_pad"), 0.0)}
    CHANNELS = (
        ChannelDef("kick/snare", ("kick", "snare"), (("snare", 2),), pan=128),
        ChannelDef("hat", ("hat",), pan=164),
        ChannelDef("bass", ("bass",), pan=128),
        ChannelDef("poly pad", ("pad",), pan=80),
        ChannelDef("lead", ("lead",), pan=150),
        ChannelDef("arp", ("arp",), pan=190),
    )
    DRUM_CHANNEL = {"kick": CH_KS, "snare": CH_KS, "hat": CH_HAT}
    KEYS = (9, 4, 6)
    MODE = "aeolian"
    PROGRESSIONS = (
        ("i-VI-III-VII", (C(0, "min", label="i"), C(8, "maj", label="VI"), C(3, "maj", label="III"), C(10, "maj", label="VII"))),
        ("VI-VII-i-i", (C(8, "maj", label="VI"), C(10, "maj", label="VII"), C(0, "min", label="i"), C(0, "min", label="i"))),
        ("i-iv-VI-V", (C(0, "min", label="i"), C(5, "min", label="iv"), C(8, "maj", label="VI"), C(7, "maj", label="V"))),
    )
    SECTIONS = {
        "intro": Section("intro", prog=0, intensity=0.6, parts=frozenset({"arp", "pad"})),
        "verse": Section("verse", prog=0, intensity=0.8, parts=BASE | {"lead"}),
        "chorus": Section("chorus", prog=1, intensity=1.0, parts=BASE | {"lead"}),
        "solo": Section("solo", prog=2, intensity=0.9, parts=BASE | {"lead"}, lead_motifs="solo"),
        "outro": Section("outro", prog=0, intensity=0.5, parts=frozenset({"arp", "pad", "bass"})),
    }
    FORM = ("intro", "verse", "chorus", "verse", "chorus", "solo", "chorus", "outro")
    GROOVES = {"main": MAIN}
    BASS = BassSpec("bass", CH_BASS, kind="octave8", vol=52)
    PAD = PadSpec("pad", CH_PAD, vol=30)
    ARP = ArpSpec("arp", CH_ARP, rows=tuple(range(0, 16, 2)), vol=30, pattern="updown")
    LEAD = LeadSpec("lead", CH_LEAD, ScaleRules(leap_probability=0.25, leap_semitones=(3, 5, 7)), LEAD_MOTIFS,
                    vol=44, gate=0.9, vibrato=0x44)
