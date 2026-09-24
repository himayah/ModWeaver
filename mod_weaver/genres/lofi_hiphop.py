"""lofi-hiphop: ローファイ・ヒップホップ（DESIGN.md §6.16.16）。B6（6ch）: よれたビート、ジャジーなエレピ、レコードのノイズ。"""
from __future__ import annotations

from ..core import groove
from ..core.composer import RhythmMotif, ScaleRules
from ..core.model import ChordSpec
from ..profiles.band_common import (
    BandProfile, BassSpec, ChannelDef, CompSpec, FxSpec, LeadSpec, Section, hits, preset,
)
from ..profiles.registry import register_profile

C = ChordSpec
CH_KS, CH_HAT, CH_BASS, CH_EP, CH_LEAD, CH_FX = range(6)

BOOMBAP = (hits("kick", (0, 7, 10), 60) + hits("snare", (4, 12), 50)
           + hits("hat", range(0, 16, 2), 24) + hits("hat", (3, 11), 14, 0.4))

LEAD_MOTIFS = {
    "verse": (RhythmMotif((0, 3, 6, 10)), RhythmMotif((2, 4, 8, 12)), RhythmMotif((0, 6, 8, 11, 14))),
}
BEAT = frozenset({"drums", "bass", "comp", "fx"})


@register_profile
class LofiHiphopProfile(BandProfile):
    id = "lofi-hiphop"
    display_name = "Lo-fi Hip Hop"
    description = "ローファイ・ヒップホップ。よれたビート、ジャジーなエレピ、レコードのノイズ"
    description_en = "Lo-fi hip hop: swung beats, jazzy electric piano and vinyl noise"
    title = "Lo-fi Study Beat"
    default_filename = "LofiHiphop.mod"
    tempo_choices = (72, 76, 80, 84, 88)

    KIT = (
        ("kick", preset("drum_boombap_kick")), ("snare", preset("drum_boombap_snare")),
        ("hat", preset("nostalgic_hihat")), ("bass", preset("bass_finger")),
        ("lead", preset("swing_sax_lead", volume=38)), ("vinyl", preset("fx_vinyl")),
    )
    CHORD_KITS = {"ep": (preset("keys_ep"), 0.0)}
    CHANNELS = (
        ChannelDef("kick/snare", ("kick", "snare"), (("snare", 2),), pan=128),
        ChannelDef("hat", ("hat",), pan=164),
        ChannelDef("bass", ("bass",), pan=128),
        ChannelDef("e.piano", ("ep",), pan=90),
        ChannelDef("lead", ("lead",), pan=170),
        ChannelDef("vinyl", ("vinyl",), pan=128),
    )
    DRUM_CHANNEL = {"kick": CH_KS, "snare": CH_KS, "hat": CH_HAT}
    KEYS = (2, 5, 9, 0)
    PROGRESSIONS = (
        ("ii9-V13-Imaj9-vi7", (C(2, "m9", label="ii9"), C(7, "dom13", label="V13"), C(0, "maj9", label="Imaj9"),
                               C(9, "m7", label="vi7"))),
        ("Imaj7-iii7-vi7-IVmaj7", (C(0, "maj7", label="Imaj7"), C(4, "m7", label="iii7"), C(9, "m7", label="vi7"),
                                   C(5, "maj7", label="IVmaj7"))),
        ("IVmaj9-iii7-ii9-Imaj9", (C(5, "maj9", label="IVmaj9"), C(4, "m7", label="iii7"), C(2, "m9", label="ii9"),
                                   C(0, "maj9", label="Imaj9"))),
    )
    SECTIONS = {
        "intro": Section("intro", prog=0, intensity=0.4, parts=frozenset({"comp", "fx"})),
        "a": Section("a", prog=0, intensity=0.7, parts=BEAT | {"lead"}),
        "b": Section("b", prog=1, intensity=0.7, parts=BEAT | {"lead"}),
        "outro": Section("outro", prog=0, intensity=0.4, parts=frozenset({"comp", "fx", "bass"})),
    }
    FORM = ("intro", "a", "a", "b", "a", "outro")
    GROOVES = {"main": BOOMBAP}
    SWING = groove.SwingConfig(long_speed=7, short_speed=5)
    BASS = BassSpec("bass", CH_BASS, kind="boombap", vol=56)
    COMP = CompSpec("ep", CH_EP, kind="charleston", vol=42, wobble=0x22)
    FX = FxSpec("vinyl", CH_FX, every=2, vol=22)
    LEAD = LeadSpec("lead", CH_LEAD, ScaleRules(leap_probability=0.2, leap_semitones=(3, 4, 5), dissonance_weight=0.1),
                    LEAD_MOTIFS, vol=40, gate=0.8)
