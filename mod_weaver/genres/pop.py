"""pop: 明るいポップ（DESIGN.md §6.16.11）。B6（6ch）: kick/snare・hat・bass・piano・lead・pad。"""
from __future__ import annotations

from ..core.composer import RhythmMotif, ScaleRules
from ..core.model import ChordSpec
from ..profiles.band_common import (
    BandProfile, BassSpec, ChannelDef, CompSpec, LeadSpec, PadSpec, Section, hits, preset,
)
from ..profiles.registry import register_profile

C = ChordSpec
CH_KS, CH_HAT, CH_BASS, CH_KEYS, CH_LEAD, CH_PAD = range(6)

MAIN = (hits("kick", (0, 8, 10), 58) + hits("snare", (4, 12), 50)
        + hits("hat", range(0, 16, 2), 30) + hits("shaker", (1, 3, 5, 7, 9, 11, 13, 15), 18, 0.5))
VERSE = hits("kick", (0, 10), 54) + hits("snare", (4, 12), 44) + hits("shaker", range(0, 16, 2), 22)
FILL = hits("snare", (8, 10, 12, 13, 14, 15), 46)
CRASH = hits("crash", (0,), 54)

LEAD_MOTIFS = {
    "verse": (RhythmMotif((0, 4, 6, 8, 12)), RhythmMotif((2, 4, 8, 10, 12)), RhythmMotif((0, 3, 6, 8, 11))),
    "chorus": (RhythmMotif((0, 2, 4, 8, 10, 12)), RhythmMotif((0, 4, 6, 8, 12, 14)), RhythmMotif((0, 2, 6, 8, 12))),
}
BASE = frozenset({"drums", "bass", "comp", "pad"})


@register_profile
class PopProfile(BandProfile):
    id = "pop"
    display_name = "Pop"
    description = "ポップ。長調の明るいメロディとピアノ、覚えやすいサビ"
    description_en = "Pop: bright major-key melodies, piano and a catchy chorus"
    title = "Bright Pop"
    default_filename = "Pop.mod"
    tempo_choices = (100, 104, 108, 112, 116, 120)

    KIT = (
        ("kick", preset("drum_pop_kick")), ("snare", preset("drum_pop_snare")), ("hat", preset("nostalgic_hihat")),
        ("shaker", preset("perc_shaker")), ("crash", preset("march_crash_cymbal")), ("bass", preset("bass_finger")),
        ("lead", preset("vox_ooh")),
    )
    CHORD_KITS = {"piano": (preset("keys_piano"), 0.0), "pad": (preset("pad_warm"), 0.0)}
    CHANNELS = (
        ChannelDef("kick/snare", ("kick", "snare"), (("snare", 2),), pan=128),
        ChannelDef("hat", ("hat", "shaker", "crash"), (("crash", 3), ("hat", 2)), pan=160),
        ChannelDef("bass", ("bass",), pan=128),
        ChannelDef("piano", ("piano",), pan=88),
        ChannelDef("lead", ("lead",), pan=168),
        ChannelDef("pad", ("pad",), pan=64),
    )
    DRUM_CHANNEL = {"kick": CH_KS, "snare": CH_KS, "hat": CH_HAT, "shaker": CH_HAT, "crash": CH_HAT}
    KEYS = (0, 2, 5, 7)
    PROGRESSIONS = (
        ("I-V-vi-IV", (C(0, "maj", label="I"), C(7, "maj", label="V"), C(9, "min", label="vi"), C(5, "maj", label="IV"))),
        ("vi-IV-I-V", (C(9, "min", label="vi"), C(5, "maj", label="IV"), C(0, "maj", label="I"), C(7, "maj", label="V"))),
        ("I-vi-IV-V", (C(0, "maj", label="I"), C(9, "min", label="vi"), C(5, "maj", label="IV"), C(7, "maj", label="V"))),
        ("IV-V-iii-vi", (C(5, "maj7", label="IVmaj7"), C(7, "maj", label="V"), C(4, "m7", label="iii7"),
                         C(9, "min", label="vi"))),
    )
    N_PROGRESSIONS = 3
    SECTIONS = {
        "intro": Section("intro", prog=0, intensity=0.4, parts=frozenset({"comp", "pad"})),
        "verse": Section("verse", prog=1, intensity=0.6, parts=BASE | {"lead"}, groove="verse"),
        "pre": Section("pre", prog=2, intensity=0.7, parts=BASE | {"lead"}, fill=True),
        "chorus": Section("chorus", prog=0, intensity=1.0, parts=BASE | {"lead"}, crash=True, fill=True,
                          lead_motifs="chorus"),
        "bridge": Section("bridge", prog=2, intensity=0.5, parts=frozenset({"bass", "comp", "pad", "lead"})),
        "chorus_up": Section("chorus_up", prog=0, intensity=1.0, parts=BASE | {"lead"}, key_offset=1,
                             crash=True, lead_motifs="chorus"),
        "outro": Section("outro", prog=0, intensity=0.4, parts=frozenset({"comp", "pad", "bass"})),
    }
    FORM = ("intro", "verse", "pre", "chorus", "verse", "pre", "chorus", "bridge", "chorus", "chorus_up", "outro")
    GROOVES = {"main": MAIN, "verse": VERSE, "fill": FILL, "crash": CRASH}
    BASS = BassSpec("bass", CH_BASS, kind="root8", vol=54)
    COMP = CompSpec("piano", CH_KEYS, kind="pulse8", vol=40)
    PAD = PadSpec("pad", CH_PAD, vol=28)
    LEAD = LeadSpec("lead", CH_LEAD, ScaleRules(leap_probability=0.2, leap_semitones=(3, 4, 5, 7)), LEAD_MOTIFS,
                    vol=50, gate=0.85, vibrato=0x32)
