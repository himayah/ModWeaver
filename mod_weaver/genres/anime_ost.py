"""anime-ost: アニメの劇伴風（DESIGN.md §6.16.28）。B6（6ch）: 刻むストリングスとジャズの和声、ブラスの決め。

主題はサックス（A）とヴァイオリン（B）が持ち替え、クライマックスはブラスが歌う（``lead_key``）。ブラスの「決め」は
イントロ・ブレイク・最後に、ピアノの和音・クラッシュと同時に鳴らす。"""
from __future__ import annotations

from ..core.composer import RhythmMotif, ScaleRules
from ..core.model import ChordSpec
from ..core.pitch import fold_into_range
from ..profiles.band_common import (
    BandProfile, BassSpec, ChannelDef, CompSpec, LeadSpec, Section, _scale_vol, hits, preset,
)
from ..profiles.registry import register_profile

C = ChordSpec
CH_KS, CH_CYM, CH_BASS, CH_PIANO, CH_LEAD, CH_STR = range(6)

MAIN = (hits("kick", (0, 10), 56) + hits("snare", (4, 12), 46) + hits("snare", (7, 15), 22, 0.5)
        + hits("ride", (0, 4, 6, 8, 12, 14), 30))
BREAK = (hits("kick", (0, 3, 6, 10), 58) + hits("snare", (4, 12), 52) + hits("snare", (9, 13, 14, 15), 36, 0.8)
         + hits("ride", (0, 6, 8, 14), 30))
FILL = hits("snare", (8, 10, 12, 13, 14, 15), 48)
CRASH = hits("crash", (0,), 56)
KIME = (0, 3, 6)                               # 決めのリズム（16分の 3+3）
SPIC_ACCENTS = (0, 3, 6, 8, 11, 14)

LEAD_MOTIFS = {
    "verse": (RhythmMotif((0, 3, 6, 8, 12)), RhythmMotif((0, 2, 4, 6, 10)), RhythmMotif((0, 4, 6, 8, 10, 14))),
    "climax": (RhythmMotif((0, 6, 8)), RhythmMotif((0, 4, 8, 12)), RhythmMotif((0, 3, 6, 12))),
}
BAND = frozenset({"drums", "bass", "comp"})
LEAD_BY_SECTION = {"b": "vln", "climax": "brass"}


@register_profile
class AnimeOstProfile(BandProfile):
    id = "anime-ost"
    category = "style"
    display_name = "Anime Soundtrack"
    description = "アニメ劇伴風。刻むストリングスとジャズの和声、ブラスの決め"
    description_en = "Anime soundtrack style: driving strings with jazz harmony and brass hits"
    title = "Anime Soundtrack"
    default_filename = "AnimeOST.mod"
    tempo_choices = (120, 126, 132, 138, 144, 150)

    KIT = (
        ("kick", preset("prog_kick")), ("snare", preset("swing_brush_snare")), ("ride", preset("swing_ride")),
        ("crash", preset("march_crash_cymbal")), ("bass", preset("swing_walk_bass")),
        ("sax", preset("swing_sax_lead")), ("vln", preset("orch_violin")), ("brass", preset("march_brass_section")),
        ("spic", preset("str_spiccato", volume=40)),
    )
    CHORD_KITS = {"piano": (preset("keys_piano", volume=42), 0.0)}
    CHANNELS = (
        ChannelDef("kick/snare", ("kick", "snare"), (("snare", 2),), pan=128),
        ChannelDef("ride/crash", ("ride", "crash"), (("crash", 2),), pan=170),
        ChannelDef("bass", ("bass",), pan=128),
        ChannelDef("piano", ("piano",), pan=88),
        ChannelDef("lead", ("sax", "vln", "brass"), pan=150),
        ChannelDef("strings/brass", ("spic", "brass"), (("brass", 2),), pan=64),
    )
    DRUM_CHANNEL = {"kick": CH_KS, "snare": CH_KS, "ride": CH_CYM, "crash": CH_CYM}
    KEYS = (2, 7)
    MODE = "aeolian"
    PROGRESSIONS = (
        ("i-iv-VII-III", (C(0, "m7", label="im7"), C(5, "m7", label="ivm7"), C(10, "dom7", label="VII7"),
                          C(3, "maj7", label="IIImaj7"))),
        ("iim7b5-V7-i", (C(2, "m7b5", label="iim7b5"), C(7, "dom7", label="V7"), C(0, "m7", label="im7"),
                         C(0, "m7", label="im7"))),
        ("VImaj7-V7-i", (C(8, "maj7", label="VImaj7"), C(7, "dom7", label="V7"), C(0, "m7", label="im7"),
                         C(0, "m7", label="im7"))),
    )
    N_PROGRESSIONS = 3
    SECTIONS = {
        "intro": Section("intro", prog=0, intensity=0.8, parts=BAND | {"spic", "kime"}, crash=True),
        "a": Section("a", prog=0, intensity=0.75, parts=BAND | {"lead"}, fill=True),
        "b": Section("b", prog=1, intensity=0.85, parts=BAND | {"lead", "spic"}, fill=True),
        "break": Section("break", prog=2, intensity=0.9, parts=frozenset({"drums", "bass", "kime"}), groove="break",
                         crash=True),
        "climax": Section("climax", prog=2, intensity=1.0, parts=BAND | {"lead", "spic"}, crash=True,
                          lead_motifs="climax"),
        "outro": Section("outro", prog=0, intensity=0.9, parts=BAND | {"spic", "kime"}),
    }
    FORM = ("intro", "a", "b", "break", "a", "b", "climax", "outro")
    GROOVES = {"main": MAIN, "break": BREAK, "fill": FILL, "crash": CRASH}
    BASS = BassSpec("bass", CH_BASS, kind="walking", vol=54)
    COMP = CompSpec("piano", CH_PIANO, kind="charleston", vol=40)
    LEAD = LeadSpec("sax", CH_LEAD, ScaleRules(leap_probability=0.3, leap_semitones=(3, 4, 5, 7)), LEAD_MOTIFS,
                    vol=46, gate=0.85, vibrato=0x23)

    def lead_key(self, sec):
        return LEAD_BY_SECTION.get(sec.kind, "sax")

    def compose_measure(self, mctx, st, rng, buf):
        sec = self.SECTIONS[mctx.pattern.kind]
        if sec.kind == "outro" and mctx.is_last:
            self._kime(mctx, sec, buf, final=True)           # 最後は決めで終わる
            return
        super().compose_measure(mctx, st, rng, buf)

    def extra_measure(self, mctx, sec, st, rng, buf):
        ins = mctx.instruments
        m = mctx.measure_idx
        if "kime" in sec.parts and m % 2 == 0:
            self._kime(mctx, sec, buf)
        elif "spic" in sec.parts:
            spic = ins["spic"]
            root = fold_into_range(mctx.chord.bass, 12, 23)
            tones = [root, root, fold_into_range(mctx.chord.bass + 7, 12, 23), root + 12 if root + 12 <= 30 else root]
            for row in range(16):
                vol = _scale_vol(40 if row in SPIC_ACCENTS else 26, sec)
                buf.put(row, CH_STR, spic.cell(tones[(row // 2) % len(tones)] if row % 2 == 0 else root, vol=vol))
        elif m == 0:
            buf.put(0, CH_STR, ins["brass"].off())

    def _kime(self, mctx, sec, buf, *, final: bool = False) -> None:
        """ブラス・ピアノ（和音のある区間だけ）・ベース・キック・クラッシュの決め（16分の 3+3。最後は3つ目を伸ばす）。
        他のパートより優先して置き換える。"""
        ins = mctx.instruments
        chord = mctx.chord
        brass = ins["brass"]
        piano = ins[self._chord_key("piano", mctx)]
        top = fold_into_range(chord.harmony + 7, 14, 26)
        for i, row in enumerate(KIME):
            buf.replace(row, CH_STR, brass.cell(top, vol=_scale_vol(50, sec)))
            if "comp" in sec.parts:
                buf.replace(row, CH_PIANO, piano.cell(chord.harmony, vol=_scale_vol(46, sec)))
            buf.replace(row, CH_BASS, ins["bass"].cell(chord.bass, vol=_scale_vol(54, sec)))
            buf.replace(row, CH_KS, ins["kick"].cell(vol=56))
        buf.replace(0, CH_CYM, ins["crash"].cell(vol=56))
        if not final:
            buf.replace(KIME[-1] + 2, CH_STR, brass.off())
        else:
            buf.replace(0, CH_LEAD, brass.off())
