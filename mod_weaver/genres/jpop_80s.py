"""jpop-80s: 80年代 J-POP 風（DESIGN.md §6.16.26）。B6（6ch）: 王道進行、ゲートスネア、シンセブラスの決め、最後のサビで転調。"""
from __future__ import annotations

from ..core.composer import RhythmMotif, ScaleRules
from ..core.midi import GmVoice
from ..core.model import ChordSpec
from ..profiles.band_common import (
    BandProfile, BassSpec, ChannelDef, CompSpec, EchoSpec, Fold, LayerSpec, LeadSpec, PadSpec, Section, hits, keep,
    preset,
)
from ..profiles.registry import register_profile

C = ChordSpec
# 7・8 番目の論理チャンネルは 8ch の編成だけで鳴らす任意パート（DESIGN.md §6.14）
CH_KS, CH_HAT, CH_BASS, CH_KEYS, CH_LEAD, CH_BRASS, CH_X_LEAD_ECHO, CH_X_STRINGS = range(8)

MAIN = hits("kick", (0, 8, 10), 58) + hits("snare", (4, 12), 54) + hits("hat", range(16), 22, 0.9) + hits("tamb", (4, 12), 26)
FILL = hits("snare", (8, 10, 12, 13, 14, 15), 50)
CRASH = hits("crash", (0,), 56)
KIME = (0, 3, 6)                               # ブラスの「決め」（イントロ・サビ頭）

LEAD_MOTIFS = {
    "verse": (RhythmMotif((0, 2, 4, 6, 8, 12)), RhythmMotif((0, 4, 6, 8, 10, 12))),
    "chorus": (RhythmMotif((0, 2, 4, 8, 10, 12, 14)), RhythmMotif((0, 4, 6, 8, 12)), RhythmMotif((0, 2, 6, 8, 12))),
}
BAND = frozenset({"drums", "bass", "comp"})


@register_profile
class JPop80sProfile(BandProfile):
    id = "jpop-80s"
    category = "style"
    display_name = "80s J-Pop"
    description = "80年代 J-POP 風。明るいコードと都会的なブラス、軽快なビートと最後のサビの転調"
    description_en = "80s J-pop style: bright chords, city brass, a light beat and a final key change"
    title = "J-Pop 80s"
    default_filename = "JPop80s.mod"
    tempo_choices = (120, 124, 128, 132, 136)

    KIT = (
        ("kick", preset("drum_pop_kick")), ("snare", preset("drum_gated_snare")), ("hat", preset("nostalgic_hihat")),
        ("tamb", preset("perc_tambourine")), ("crash", preset("march_crash_cymbal")), ("bass", preset("bass_finger")),
        ("lead", preset("syn_square_lead")),
        ("line", preset("orch_violin", volume=30)),
    )
    CHORD_KITS = {"ep": (preset("keys_ep"), 0.0), "brass": (preset("syn_poly_pad", name="BrassPad"), 0.0)}
    GM = {"brass": GmVoice(program=62)}
    CHANNELS = (
        ChannelDef("kick/snare", ("kick", "snare"), (("snare", 2),), pan=128),
        ChannelDef("hat", ("hat", "tamb", "crash"), (("crash", 3), ("tamb", 2)), pan=164),
        ChannelDef("bass", ("bass",), pan=128),
        ChannelDef("e.piano", ("ep",), pan=84),
        ChannelDef("lead", ("lead",), pan=172),
        ChannelDef("synth brass", ("brass",), pan=56),
        ChannelDef("lead echo", ("lead",), pan=96),
        ChannelDef("strings", ("line",), pan=160),
    )
    DRUM_CHANNEL = {"kick": CH_KS, "snare": CH_KS, "hat": CH_HAT, "tamb": CH_HAT, "crash": CH_HAT}
    KEYS = (0, 2, 4)
    PROGRESSIONS = (
        ("IVmaj7-V7-iii7-vi", (C(5, "maj7", label="IVmaj7"), C(7, "dom7", label="V7"), C(4, "m7", label="iii7"),
                               C(9, "min", label="vi"))),
        ("I-V-vi-iii", (C(0, "maj", label="I"), C(7, "maj", label="V"), C(9, "min", label="vi"), C(4, "min", label="iii"))),
        ("ii7-V7-Imaj7-vi7", (C(2, "m7", label="ii7"), C(7, "dom7", label="V7"), C(0, "maj7", label="Imaj7"),
                              C(9, "m7", label="vi7"))),
    )
    N_PROGRESSIONS = 3
    SECTIONS = {
        "intro": Section("intro", prog=0, intensity=0.9, parts=BAND | {"pad"}, crash=True, fill=True),
        "a": Section("a", prog=1, intensity=0.7, parts=BAND | {"lead"}),
        "b": Section("b", prog=2, intensity=0.8, parts=BAND | {"lead", "pad"}, fill=True),
        "sabi": Section("sabi", prog=0, intensity=1.0, parts=BAND | {"lead", "pad"}, crash=True, fill=True,
                        lead_motifs="chorus"),
        "interlude": Section("interlude", prog=0, intensity=0.8, parts=BAND | {"pad"}),
        "sabi_up": Section("sabi_up", prog=0, intensity=1.0, parts=BAND | {"lead", "pad"}, key_offset=2, crash=True,
                           lead_motifs="chorus"),
        "outro": Section("outro", prog=0, intensity=0.8, parts=BAND | {"pad"}, key_offset=2, crash=True),
    }
    FORM = ("intro", "a", "b", "sabi", "interlude", "a", "b", "sabi", "sabi_up", "outro")
    GROOVES = {"main": MAIN, "fill": FILL, "crash": CRASH}
    BASS = BassSpec("bass", CH_BASS, kind="octave8", vol=54)
    COMP = CompSpec("ep", CH_KEYS, kind="half", vol=40)
    PAD = PadSpec("brass", CH_BRASS, vol=38)
    LEAD = LeadSpec("lead", CH_LEAD, ScaleRules(leap_probability=0.25, leap_semitones=(3, 4, 5, 7)), LEAD_MOTIFS,
                    vol=46, gate=0.8, vibrato=0x33)

    ECHO = (EchoSpec(CH_LEAD, CH_X_LEAD_ECHO, delay=3, ratio=0.45, offs=True),)
    LAYERS = (LayerSpec("line", CH_X_STRINGS, follow="lead", vol=26, register=(19, 31)),)
    ARRANGEMENTS = {                          # DESIGN.md §6.14: 4ch＝小編成、6ch＝標準、8ch＝任意パートを足す
        4: (Fold("drums", ("kick/snare", "hat"), (("snare", 4), ("kick", 3), ("crash", 2))),
            *keep("bass", "e.piano", "lead")),
        6: keep("kick/snare", "hat", "bass", "e.piano", "lead", "synth brass"),
        8: keep("kick/snare", "hat", "bass", "e.piano", "lead", "synth brass", "lead echo", "strings"),
    }
    def pad(self, mctx, sec, rng, buf):
        """シンセブラス: サビ・イントロの頭は「決め」（短い3連打）、それ以外は和音を伸ばす。"""
        inst = mctx.instruments[self._chord_key("brass", mctx)]
        vol = round(40 * (0.6 + 0.4 * sec.intensity))
        if sec.crash and mctx.measure_idx == 0:
            for row in KIME:
                buf.put(row, CH_BRASS, inst.cell(mctx.chord.harmony, vol=vol))
            buf.put(KIME[-1] + 2, CH_BRASS, inst.off())
        elif self._is_chord_change(mctx):
            buf.put(0, CH_BRASS, inst.cell(mctx.chord.harmony, vol=vol - 6))
