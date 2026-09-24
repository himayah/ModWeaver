"""rock: ギター主体のロック（DESIGN.md §6.16.10）。B6（6ch）: kick/snare・hat/cymbal・bass・rhythm gtr・lead gtr・tom。"""
from __future__ import annotations

from ..core.composer import RhythmMotif, ScaleRules
from ..core.model import ChordSpec
from ..profiles.band_common import (
    BandProfile, BassSpec, ChannelDef, CompSpec, EchoSpec, Fold, LayerSpec, LeadSpec, Section, hits, keep, preset,
)
from ..profiles.registry import register_profile

C = ChordSpec
CH_KS, CH_CYM, CH_BASS, CH_GTR, CH_LEAD, CH_TOM, CH_X_LEAD_ECHO, CH_X_ORGAN = range(8)   # 7・8 番目は 8ch の編成だけ

MAIN = hits("kick", (0, 8, 10), 60) + hits("snare", (4, 12), 54) + hits("hat", range(0, 16, 2), 32)
RIDE = hits("kick", (0, 8, 10), 60) + hits("snare", (4, 12), 56) + hits("ride", range(0, 16, 2), 34)
FILL = hits("tom", (8, 10), 50, notes=(27, 21)) + hits("snare", (12, 13, 14, 15), 50)   # ハイタム→ロータム
CRASH = hits("crash", (0,), 58)

LEAD_MOTIFS = {
    "verse": (RhythmMotif((0, 4, 6, 8, 12)), RhythmMotif((0, 2, 6, 10, 12)), RhythmMotif((0, 6, 8, 12, 14))),
    "chorus": (RhythmMotif((0, 4, 8, 12)), RhythmMotif((0, 2, 4, 8, 12, 14))),
    "solo": (RhythmMotif((0, 2, 3, 4, 6, 8, 10, 11, 12, 14)), RhythmMotif((0, 1, 2, 4, 6, 7, 8, 12, 14))),
}
BAND = frozenset({"drums", "bass", "comp"})


@register_profile
class RockProfile(BandProfile):
    id = "rock"
    display_name = "Rock"
    description = "ロック。ギターのリフと8ビート、4/4 の中〜速いテンポ"
    description_en = "Rock: guitar riffs over a straight eight-beat"
    title = "Rock Anthem"
    default_filename = "Rock.mod"
    tempo_choices = (112, 116, 120, 124, 128, 132)

    KIT = (
        ("kick", preset("prog_kick")), ("snare", preset("prog_snare")), ("hat", preset("nostalgic_hihat")),
        ("ride", preset("swing_ride")), ("crash", preset("march_crash_cymbal")), ("tom", preset("drum_tom")),
        ("bass", preset("bass_pick")), ("gtr", preset("gtr_crunch")), ("lead", preset("prog_lead_gtr")),
        ("organ", preset("keys_organ", volume=30)),
    )
    CHANNELS = (
        ChannelDef("kick/snare", ("kick", "snare"), (("snare", 2),), pan=128),
        ChannelDef("cymbal", ("hat", "ride", "crash"), (("crash", 3),), pan=150),
        ChannelDef("bass", ("bass",), pan=128),
        ChannelDef("rhythm gtr", ("gtr",), pan=72),
        ChannelDef("lead gtr", ("lead",), pan=184),
        ChannelDef("tom", ("tom",), pan=110),
        ChannelDef("lead echo", ("lead",), pan=96),
        ChannelDef("organ", ("organ",), pan=160),
    )
    DRUM_CHANNEL = {"kick": CH_KS, "snare": CH_KS, "hat": CH_CYM, "ride": CH_CYM, "crash": CH_CYM, "tom": CH_TOM}
    KEYS = (4, 9, 2)                           # E / A / D
    MODE = "mixolydian"
    PROGRESSIONS = (
        ("I-bVII-IV-I", (C(0, "maj", label="I"), C(10, "maj", label="bVII"), C(5, "maj", label="IV"), C(0, "maj", label="I"))),
        ("I-IV-V-IV", (C(0, "maj", label="I"), C(5, "maj", label="IV"), C(7, "maj", label="V"), C(5, "maj", label="IV"))),
        ("i-bVI-bVII-i", (C(0, "min", label="i"), C(8, "maj", label="bVI"), C(10, "maj", label="bVII"), C(0, "min", label="i"))),
    )
    SECTIONS = {
        "intro": Section("intro", prog=0, intensity=0.7, parts=frozenset({"comp", "drums"}), crash=True),
        "verse": Section("verse", prog=0, intensity=0.7, parts=BAND | {"lead"}, fill=True),
        "chorus": Section("chorus", prog=1, intensity=1.0, parts=BAND | {"lead"}, groove="ride", crash=True,
                          fill=True, lead_motifs="chorus"),
        "solo": Section("solo", prog=0, intensity=0.9, parts=BAND | {"lead"}, lead_motifs="solo", fill=True),
        "outro": Section("outro", prog=0, intensity=0.8, parts=BAND, crash=True),
    }
    FORM = ("intro", "verse", "chorus", "verse", "chorus", "solo", "chorus", "outro")
    GROOVES = {"main": MAIN, "ride": RIDE, "fill": FILL, "crash": CRASH}
    BASS = BassSpec("bass", CH_BASS, kind="root8", vol=56)
    COMP = CompSpec("gtr", CH_GTR, kind="pulse8", vol=44, chordal=False)
    LEAD = LeadSpec("lead", CH_LEAD, ScaleRules(leap_probability=0.3, leap_semitones=(3, 5, 7), dissonance_weight=0.05),
                    LEAD_MOTIFS, vol=48, gate=0.9, vibrato=0x44)

    ECHO = (EchoSpec(CH_LEAD, CH_X_LEAD_ECHO, delay=3, ratio=0.45, offs=True),)
    LAYERS = (LayerSpec("organ", CH_X_ORGAN, follow="lead", vol=26),)
    ARRANGEMENTS = {                          # DESIGN.md §6.14: 4ch＝小編成、6ch＝標準、8ch＝任意パートを足す
        4: (Fold("drums", ("kick/snare", "cymbal", "tom"), (("snare", 4), ("kick", 3), ("tom", 3), ("crash", 2))),
            *keep("bass", "rhythm gtr", "lead gtr")),
        6: keep("kick/snare", "cymbal", "bass", "rhythm gtr", "lead gtr", "tom"),
        8: keep("kick/snare", "cymbal", "bass", "rhythm gtr", "lead gtr", "tom", "lead echo", "organ"),
    }
    def comp(self, mctx, sec, rng, buf):
        """パワーコードのリフ: 根音を8分で刻み、2小節ごとに5度・短7度へ動く（ミクソリディアンのリフ）。"""
        inst = mctx.instruments["gtr"]
        root = mctx.chord.harmony
        riff = (0, 0, 0, 0, 7, 7, 10, 7) if mctx.measure_idx % 2 else (0, 0, 0, 0, 0, 0, 3, 5)
        for i, row in enumerate(range(0, 16, 2)):
            note = root + riff[i] if root + riff[i] <= self.REGISTERS.harmony[1] + 10 else root
            vol = 46 if i % 4 == 0 else 38
            buf.put(row, CH_GTR, inst.cell(note, vol=round(vol * (0.6 + 0.4 * sec.intensity))))
