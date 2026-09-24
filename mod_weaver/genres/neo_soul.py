"""neo-soul: ネオ・ソウル風（DESIGN.md §6.16.35）。B6（6ch）: 強い16分スウィングとよれたビート、エレピの豊かなテンション。"""
from __future__ import annotations

from ..core import groove
from ..core.composer import RhythmMotif, ScaleRules
from ..core.model import ChordSpec
from ..profiles.band_common import (
    BandProfile, BassSpec, ChannelDef, CompSpec, EchoSpec, Fold, LayerSpec, LeadSpec, PadSpec, Section, hits, keep,
    preset,
)
from ..profiles.registry import register_profile

C = ChordSpec
CH_KS, CH_HAT, CH_BASS, CH_EP, CH_LEAD, CH_EP2, CH_X_VOCAL_ECHO, CH_X_GUITAR = range(8)   # 7・8 番目は 8ch の編成だけ

MAIN = (hits("kick", (0, 3, 10), 58) + hits("kick", (7,), 44, 0.5) + hits("snare", (4, 12), 48)
        + hits("hat", range(0, 16, 2), 26) + hits("hat", (5, 13), 16, 0.5) + hits("rim", (15,), 22, 0.5))

LEAD_MOTIFS = {
    "verse": (RhythmMotif((1, 4, 6, 9, 12)), RhythmMotif((0, 3, 6, 10, 13)), RhythmMotif((2, 5, 8, 11, 14))),
    "chorus": (RhythmMotif((0, 3, 4, 8, 11, 12)), RhythmMotif((0, 2, 6, 8, 12))),
}
BAND = frozenset({"drums", "bass", "comp", "pad"})


@register_profile
class NeoSoulProfile(BandProfile):
    id = "neo-soul"
    category = "style"
    display_name = "Neo Soul"
    description = "ネオソウル風。よれたビートとエレピ主体の豊かなテンションコード"
    description_en = "Neo soul style: laid-back off-grid beats and lush electric piano chords"
    title = "Neo Soul Groove"
    default_filename = "NeoSoul.mod"
    tempo_choices = (80, 84, 88, 92, 96)

    KIT = (
        ("kick", preset("drum_boombap_kick")), ("snare", preset("drum_pop_snare")), ("hat", preset("nostalgic_hihat")),
        ("rim", preset("drum_rim")), ("bass", preset("bass_finger")), ("lead", preset("vox_ooh")),
        ("gtr", preset("gtr_clean_arp", volume=34)),
    )
    CHORD_KITS = {"ep": (preset("keys_ep"), 0.0)}
    CHANNELS = (
        ChannelDef("kick/snare", ("kick", "snare"), (("snare", 2),), pan=128),
        ChannelDef("hat", ("hat", "rim"), (("rim", 2),), pan=164),
        ChannelDef("bass", ("bass",), pan=128),
        ChannelDef("e.piano", ("ep",), pan=84),
        ChannelDef("vocal", ("lead",), pan=150),
        ChannelDef("e.piano 2", ("ep",), pan=180),
        ChannelDef("vocal echo", ("lead",), pan=96),
        ChannelDef("guitar", ("gtr",), pan=160),
    )
    DRUM_CHANNEL = {"kick": CH_KS, "snare": CH_KS, "hat": CH_HAT, "rim": CH_HAT}
    KEYS = (3, 8, 5)
    MODE = "dorian"
    PROGRESSIONS = (
        ("IVmaj9-iii7-vi9", (C(3, "maj9", label="bIIImaj9"), C(2, "m7", label="ii7"), C(5, "m9", label="iv9"),
                             C(0, "m11", label="i11"))),
        ("ii9-V13-iii7-VI7", (C(2, "m9", label="ii9"), C(7, "dom13", label="V13"), C(4, "m7", label="iii7"),
                              C(9, "dom9", label="VI9"))),
        ("i11-IV9", (C(0, "m11", label="i11"), C(5, "dom9", label="IV9"))),
    )
    SECTIONS = {
        "intro": Section("intro", prog=1, intensity=0.5, parts=frozenset({"comp", "pad"})),
        "verse": Section("verse", prog=0, intensity=0.7, parts=BAND | {"lead"}),
        "chorus": Section("chorus", prog=1, intensity=0.9, parts=BAND | {"lead"}, lead_motifs="chorus"),
        "bridge": Section("bridge", prog=0, intensity=0.6, parts=frozenset({"drums", "bass", "comp"})),
        "outro": Section("outro", prog=1, intensity=0.5, parts=frozenset({"comp", "bass", "pad"})),
    }
    FORM = ("intro", "verse", "chorus", "verse", "chorus", "bridge", "chorus", "outro")
    GROOVES = {"main": MAIN}
    SWING = groove.SwingConfig(long_speed=8, short_speed=4)    # 強い16分スウィング（2:1）
    LATE = (("snare", 0.35), ("hat", 0.25))                    # 一部を EDx で遅らせて「よれ」を出す
    BASS = BassSpec("bass", CH_BASS, kind="synco16", vol=56)
    COMP = CompSpec("ep", CH_EP, kind="stab2", vol=42, wobble=0x23)
    PAD = PadSpec("ep", CH_EP2, vol=30)
    LEAD = LeadSpec("lead", CH_LEAD, ScaleRules(leap_probability=0.25, leap_semitones=(3, 4, 5, 7),
                                                dissonance_weight=0.12), LEAD_MOTIFS, vol=46, gate=0.9, vibrato=0x42)
    ECHO = (EchoSpec(CH_LEAD, CH_X_VOCAL_ECHO, delay=3, ratio=0.45, offs=True),)
    LAYERS = (LayerSpec("gtr", CH_X_GUITAR, follow="lead", vol=30, register=(19, 31)),)
    ARRANGEMENTS = {                          # DESIGN.md §6.14: 4ch＝小編成、6ch＝標準、8ch＝任意パートを足す
        4: (Fold("drums", ("kick/snare", "hat"), (("snare", 4), ("kick", 3), ("rim", 2))),
            *keep("bass", "e.piano", "vocal")),
        6: keep("kick/snare", "hat", "bass", "e.piano", "vocal", "e.piano 2"),
        8: keep("kick/snare", "hat", "bass", "e.piano", "vocal", "e.piano 2", "vocal echo", "guitar"),
    }
