"""jazz: モーダル・ジャズ（DESIGN.md §12.7.12）。B4 の読み替え（4ch、Amiga 互換）: ライドとブラシ、ウォーキング・ベース、
4度堆積のピアノ、ミュート・トランペット。8分格子（1 measure＝8 row、1拍＝2 row）で8分スウィング。

形式は AABA のモーダル形式（1 pattern＝8小節）: A＝主調のドリアン、B＝半音上のドリアン。"""
from __future__ import annotations

from ..core import groove
from ..core.composer import RhythmMotif, ScaleRules
from ..core.midi import GmVoice
from ..core.model import ChordSpec
from ..profiles.band_common import BandProfile, BassSpec, ChannelDef, CompSpec, LeadSpec, Section, hits, preset
from ..profiles.registry import register_profile

C = ChordSpec
CH_DRUMS, CH_BASS, CH_PIANO, CH_TPT = range(4)

# 8 row＝4拍。ライドの「チーン・チキ」（row 3・7 は裏拍）、ブラシは2・4拍
RIDE = hits("ride", (0, 2, 4, 6), 34) + hits("ride", (3, 7), 24) + hits("brush", (2, 6), 26, 0.8)
FILL = hits("brush", (4, 5, 6, 7), 32)

LEAD_MOTIFS = {
    "head": (RhythmMotif((0, 4)), RhythmMotif((0, 3, 4)), RhythmMotif((1, 4, 6))),
    "solo": (RhythmMotif((0, 1, 2, 4, 5, 6)), RhythmMotif((0, 2, 3, 4, 6, 7)), RhythmMotif((1, 2, 3, 5, 6))),
}
BAND = frozenset({"drums", "bass", "comp"})
FERMATA = 6                                    # coda でこの measure の頭に最後の長い和音を置き、以降は余韻だけ


@register_profile
class JazzProfile(BandProfile):
    id = "jazz"
    display_name = "Modal Jazz"
    description = "ジャズ。ドリアンのモーダルなヴァンプ、4度堆積のピアノとミュート・トランペット"
    description_en = "Modal jazz: dorian vamps, quartal piano voicings and muted trumpet"
    title = "Modal Jazz"
    default_filename = "Jazz.mod"
    tempo_choices = (120, 126, 132, 138, 144)
    rows_per_measure = 8
    rows_per_beat = 2

    KIT = (
        ("ride", preset("swing_ride")), ("brush", preset("swing_brush_snare")), ("bass", preset("swing_walk_bass")),
        ("tpt", preset("orch_trumpet", name="MuteTrumpet", volume=38)),
    )
    CHORD_KITS = {"piano": (preset("keys_piano", volume=40), 0.0)}
    GM = {"tpt": GmVoice(program=59), "piano": GmVoice(program=0)}
    CHANNELS = (
        ChannelDef("ride/brush", ("ride", "brush"), (("brush", 2),)),
        ChannelDef("bass", ("bass",)),
        ChannelDef("piano", ("piano",)),
        ChannelDef("trumpet", ("tpt",)),
    )
    DRUM_CHANNEL = {"ride": CH_DRUMS, "brush": CH_DRUMS}
    KEYS = (2,)
    MODE = "dorian"
    # 和音はほとんど動かない: im11（4度堆積）のヴァンプに、2小節ごとに1段上の4度堆積を挟む
    PROGRESSIONS = (
        ("i11 vamp", (C(0, "quartal", label="i11"), C(0, "quartal", label="i11"), C(0, "quartal", label="i11"),
                      C(2, "quartal", label="ii11"))),
    )
    N_PROGRESSIONS = 1
    SECTIONS = {
        "head_a": Section("head_a", intensity=0.7, parts=BAND | {"lead"}, lead_motifs="head"),
        "head_b": Section("head_b", intensity=0.8, parts=BAND | {"lead"}, key_offset=1, lead_motifs="head", fill=True),
        "solo_a": Section("solo_a", intensity=0.9, parts=BAND | {"lead"}, lead_motifs="solo"),
        "solo_b": Section("solo_b", intensity=1.0, parts=BAND | {"lead"}, key_offset=1, lead_motifs="solo", fill=True),
        "coda": Section("coda", intensity=0.6, parts=BAND | {"lead"}, lead_motifs="head"),
    }
    FORM = ("head_a", "head_a", "head_b", "head_a", "solo_a", "solo_a", "solo_b", "solo_a",
            "head_a", "head_a", "head_b", "coda")
    GROOVES = {"main": RIDE, "fill": FILL}
    SWING = groove.SwingConfig(long_speed=14, short_speed=10)
    BASS = BassSpec("bass", CH_BASS, kind="walking", vol=54)
    COMP = CompSpec("piano", CH_PIANO, kind="charleston", vol=38)
    LEAD = LeadSpec("tpt", CH_TPT, ScaleRules(leap_probability=0.3, leap_semitones=(3, 4, 5, 7), dissonance_weight=0.1),
                    LEAD_MOTIFS, vol=46, gate=0.95, vibrato=0x23)

    def compose_measure(self, mctx, st, rng, buf):
        """coda: 前半は head の素材、FERMATA の measure で全員が長い和音を伸ばして終わる。"""
        if mctx.pattern.kind != "coda" or mctx.measure_idx < FERMATA:
            return super().compose_measure(mctx, st, rng, buf)
        if mctx.measure_idx == FERMATA:
            ins = mctx.instruments
            chord = mctx.chord
            buf.put(0, CH_DRUMS, ins["ride"].cell(vol=40))
            buf.put(0, CH_BASS, ins["bass"].cell(chord.bass, vol=50))
            buf.put(0, CH_PIANO, ins[self._chord_key("piano", mctx)].cell(chord.harmony, vol=42))
            buf.put(0, CH_TPT, ins["tpt"].cell(chord.chord_tones[len(chord.chord_tones) // 2], vol=40))
        elif mctx.is_last:
            buf.put(4, CH_TPT, mctx.instruments["tpt"].off())
