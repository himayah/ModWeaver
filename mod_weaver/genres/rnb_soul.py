"""rnb-soul: R&B／ソウル（DESIGN.md §6.16.23）。B6（6ch）: 軽い16分スウィングのスロー・ジャム、テンションコード、歌う旋律。"""
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
CH_KS, CH_HAT, CH_BASS, CH_EP, CH_LEAD, CH_STR, CH_X_VOCAL_ECHO, CH_X_FLUTE = range(8)   # 7・8 番目は 8ch の編成だけ

MAIN = hits("kick", (0, 7, 10), 54) + hits("snare", (4, 12), 46) + hits("hat", range(0, 16, 2), 24) + hits("rim", (15,), 20, 0.4)
FILL = hits("snare", (12, 14, 15), 40)

LEAD_MOTIFS = {
    "verse": (RhythmMotif((0, 3, 4, 8, 11, 12)), RhythmMotif((2, 4, 6, 10, 12)), RhythmMotif((0, 6, 8, 9, 12))),
    "chorus": (RhythmMotif((0, 4, 6, 8, 12)), RhythmMotif((0, 2, 3, 4, 8, 12))),
}
BAND = frozenset({"drums", "bass", "comp", "pad"})


@register_profile
class RnbSoulProfile(BandProfile):
    id = "rnb-soul"
    display_name = "R&B / Soul"
    description = "R&B／ソウル。滑らかなテンションコードと歌うような旋律のスロー・ジャム"
    description_en = "R&B / soul: smooth extended chords and a singing melody in a slow jam"
    title = "Soul Slow Jam"
    default_filename = "RnbSoul.mod"
    tempo_choices = (68, 72, 76, 80, 84)

    KIT = (
        ("kick", preset("drum_pop_kick")), ("snare", preset("drum_pop_snare")), ("hat", preset("nostalgic_hihat")),
        ("rim", preset("drum_rim")), ("bass", preset("bass_finger")), ("lead", preset("vox_ooh")),
        ("flute", preset("wind_flute", volume=30)),
    )
    CHORD_KITS = {"ep": (preset("keys_ep"), 0.0), "str": (preset("pad_warm"), 0.0)}
    CHANNELS = (
        ChannelDef("kick/snare", ("kick", "snare"), (("snare", 2),), pan=128),
        ChannelDef("hat", ("hat", "rim"), (("rim", 2),), pan=160),
        ChannelDef("bass", ("bass",), pan=128),
        ChannelDef("e.piano", ("ep",), pan=88),
        ChannelDef("vocal", ("lead",), pan=140),
        ChannelDef("strings", ("str",), pan=60),
        ChannelDef("vocal echo", ("lead",), pan=96),
        ChannelDef("flute", ("flute",), pan=160),
    )
    DRUM_CHANNEL = {"kick": CH_KS, "snare": CH_KS, "hat": CH_HAT, "rim": CH_HAT}
    KEYS = (3, 8, 1)
    PROGRESSIONS = (
        ("IVmaj7-iii7-ii7-Imaj7", (C(5, "maj7", label="IVmaj7"), C(4, "m7", label="iii7"), C(2, "m7", label="ii7"),
                                   C(0, "maj7", label="Imaj7"))),
        ("ii9-V13-Imaj9-Imaj9", (C(2, "m9", label="ii9"), C(7, "dom13", label="V13"), C(0, "maj9", label="Imaj9"),
                                 C(0, "maj9", label="Imaj9"))),
        ("vi9-ii9-V7sus4-Imaj9", (C(9, "m9", label="vi9"), C(2, "m9", label="ii9"), C(7, "7sus4", label="V7sus4"),
                                  C(0, "maj9", label="Imaj9"))),
    )
    N_PROGRESSIONS = 3
    SECTIONS = {
        "intro": Section("intro", prog=1, intensity=0.5, parts=frozenset({"comp", "pad"})),
        "verse": Section("verse", prog=0, intensity=0.6, parts=BAND | {"lead"}),
        "pre": Section("pre", prog=2, intensity=0.7, parts=BAND | {"lead"}, fill=True),
        "chorus": Section("chorus", prog=1, intensity=0.9, parts=BAND | {"lead"}, fill=True, lead_motifs="chorus"),
        "bridge": Section("bridge", prog=2, intensity=0.6, parts=frozenset({"bass", "comp", "pad", "lead"})),
        "outro": Section("outro", prog=1, intensity=0.5, parts=frozenset({"comp", "pad", "bass"})),
    }
    FORM = ("intro", "verse", "pre", "chorus", "verse", "pre", "chorus", "bridge", "chorus", "outro")
    GROOVES = {"main": MAIN, "fill": FILL}
    SWING = groove.SwingConfig(long_speed=7, short_speed=5)    # 軽い16分スウィング（Speed の和 12＝半拍）
    BASS = BassSpec("bass", CH_BASS, kind="boombap", vol=56)
    COMP = CompSpec("ep", CH_EP, kind="half", vol=40, wobble=0x22)
    PAD = PadSpec("str", CH_STR, vol=26)
    LEAD = LeadSpec("lead", CH_LEAD, ScaleRules(leap_probability=0.2, leap_semitones=(3, 4, 5), dissonance_weight=0.1),
                    LEAD_MOTIFS, vol=48, gate=0.95, vibrato=0x43)
    ECHO = (EchoSpec(CH_LEAD, CH_X_VOCAL_ECHO, delay=3, ratio=0.45, offs=True),)
    LAYERS = (LayerSpec("flute", CH_X_FLUTE, follow="lead", vol=26, register=(19, 31)),)
    ARRANGEMENTS = {                          # DESIGN.md §6.14: 4ch＝小編成、6ch＝標準、8ch＝任意パートを足す
        4: (Fold("drums", ("kick/snare", "hat"), (("snare", 4), ("kick", 3), ("rim", 2))),
            *keep("bass", "e.piano", "vocal")),
        6: keep("kick/snare", "hat", "bass", "e.piano", "vocal", "strings"),
        8: keep("kick/snare", "hat", "bass", "e.piano", "vocal", "strings", "vocal echo", "flute"),
    }
