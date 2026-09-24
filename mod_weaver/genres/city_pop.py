"""city-pop: 80年代シティポップ（DESIGN.md §6.16.14）。B6（6ch）: テンションコードのエレピ、跳ねるベース、ギターのカッティング。"""
from __future__ import annotations

from ..core.composer import RhythmMotif, ScaleRules
from ..core.model import ChordSpec
from ..profiles.band_common import (
    BandProfile, BassSpec, ChannelDef, CompSpec, EchoSpec, Fold, LayerSpec, LeadSpec, PadSpec, Section, hits, keep,
    preset,
)
from ..profiles.registry import register_profile

C = ChordSpec
CH_KS, CH_HAT, CH_BASS, CH_EP, CH_LEAD, CH_CUT, CH_X_LEAD_ECHO, CH_X_STRINGS = range(8)   # 7・8 番目は 8ch の編成だけ

MAIN = (hits("kick", (0, 7, 10), 56) + hits("snare", (4, 12), 48)
        + hits("hat", range(0, 16, 2), 28) + hits("tamb", (4, 12), 24))
FILL = hits("snare", (10, 12, 13, 14, 15), 44)
CRASH = hits("crash", (0,), 50)

LEAD_MOTIFS = {
    "verse": (RhythmMotif((0, 3, 6, 8, 12)), RhythmMotif((2, 4, 7, 10, 12)), RhythmMotif((0, 4, 6, 10, 14))),
    "chorus": (RhythmMotif((0, 2, 4, 7, 10, 12)), RhythmMotif((0, 3, 6, 8, 10, 14))),
}
GROOVE = frozenset({"drums", "bass", "comp", "pad"})


@register_profile
class CityPopProfile(BandProfile):
    id = "city-pop"
    display_name = "City Pop"
    description = "シティポップ。テンションコードのエレピ、跳ねるベースとギターのカッティング"
    description_en = "City pop: jazzy electric piano, bouncy bass and funky guitar cutting"
    title = "City Pop Night"
    default_filename = "CityPop.mod"
    tempo_choices = (104, 108, 112, 116, 120)

    KIT = (
        ("kick", preset("drum_pop_kick")), ("snare", preset("drum_pop_snare")), ("hat", preset("nostalgic_hihat")),
        ("tamb", preset("perc_tambourine")), ("crash", preset("march_crash_cymbal")), ("bass", preset("bass_slap")),
        ("lead", preset("syn_brass")),
        ("line", preset("orch_violin", volume=30)),
    )
    CHORD_KITS = {"ep": (preset("keys_ep"), 0.0), "cut": (preset("gtr_clean_cut"), 0.0)}
    CHANNELS = (
        ChannelDef("kick/snare", ("kick", "snare"), (("snare", 2),), pan=128),
        ChannelDef("hat", ("hat", "tamb", "crash"), (("crash", 3), ("tamb", 2)), pan=164),
        ChannelDef("bass", ("bass",), pan=128),
        ChannelDef("e.piano", ("ep",), pan=84),
        ChannelDef("lead", ("lead",), pan=172),
        ChannelDef("cutting gtr", ("cut",), pan=48),
        ChannelDef("lead echo", ("lead",), pan=96),
        ChannelDef("strings", ("line",), pan=160),
    )
    DRUM_CHANNEL = {"kick": CH_KS, "snare": CH_KS, "hat": CH_HAT, "tamb": CH_HAT, "crash": CH_HAT}
    KEYS = (4, 9, 1)
    MODE_BY_QUALITY = {"m7": "dorian", "dom7": "mixolydian"}
    PROGRESSIONS = (
        ("IVmaj7-III7-vi7-v7", (C(5, "maj7", label="IVmaj7"), C(4, "dom7", label="III7"), C(9, "m7", label="vi7"),
                                C(7, "m7", label="v7"))),
        ("ii7-V7-Imaj7-VI7", (C(2, "m7", label="ii7"), C(7, "dom7", label="V7"), C(0, "maj7", label="Imaj7"),
                              C(9, "dom7", label="VI7"))),
        ("IVmaj7-V7-iii7-vi7", (C(5, "maj7", label="IVmaj7"), C(7, "dom9", label="V9"), C(4, "m7", label="iii7"),
                                C(9, "m9", label="vi9"))),
    )
    N_PROGRESSIONS = 3
    SECTIONS = {
        "intro": Section("intro", prog=0, intensity=0.7, parts=GROOVE, crash=True),
        "verse": Section("verse", prog=1, intensity=0.7, parts=GROOVE | {"lead"}),
        "pre": Section("pre", prog=2, intensity=0.8, parts=GROOVE | {"lead"}, fill=True),
        "chorus": Section("chorus", prog=0, intensity=1.0, parts=GROOVE | {"lead"}, crash=True, fill=True,
                          lead_motifs="chorus"),
        "interlude": Section("interlude", prog=1, intensity=0.6, parts=frozenset({"drums", "bass", "comp"})),
        "outro": Section("outro", prog=0, intensity=0.6, parts=GROOVE),
    }
    FORM = ("intro", "verse", "pre", "chorus", "interlude", "verse", "pre", "chorus", "chorus", "outro")
    GROOVES = {"main": MAIN, "fill": FILL, "crash": CRASH}
    BASS = BassSpec("bass", CH_BASS, kind="synco16", vol=56)
    COMP = CompSpec("cut", CH_CUT, kind="cutting16", vol=34)
    LEAD = LeadSpec("lead", CH_LEAD, ScaleRules(leap_probability=0.25, leap_semitones=(3, 4, 5, 7),
                                                dissonance_weight=0.08), LEAD_MOTIFS, vol=46, gate=0.8)

    PAD = PadSpec("ep", CH_EP, vol=42)

    ECHO = (EchoSpec(CH_LEAD, CH_X_LEAD_ECHO, delay=3, ratio=0.45, offs=True),)
    LAYERS = (LayerSpec("line", CH_X_STRINGS, follow="lead", vol=26, register=(19, 31)),)
    ARRANGEMENTS = {                          # DESIGN.md §6.14: 4ch＝小編成、6ch＝標準、8ch＝任意パートを足す
        4: (Fold("drums", ("kick/snare", "hat"), (("snare", 4), ("kick", 3), ("crash", 2))),
            *keep("bass", "e.piano", "lead")),
        6: keep("kick/snare", "hat", "bass", "e.piano", "lead", "cutting gtr"),
        8: keep("kick/snare", "hat", "bass", "e.piano", "lead", "cutting gtr", "lead echo", "strings"),
    }
    def pad(self, mctx, sec, rng, buf):
        """エレピは2拍ごとに和音（テンションコード）を置く。"""
        inst = mctx.instruments[self._chord_key("ep", mctx)]
        for row, vol in ((0, self.PAD.vol), (8, self.PAD.vol - 8)):
            buf.put(row, CH_EP, inst.cell(mctx.chord.harmony, vol=round(vol * (0.6 + 0.4 * sec.intensity))))
