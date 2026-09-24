"""bossa-nova: ボサノバ（DESIGN.md §12.7.13）。B4（4ch、Amiga 互換）: リムのクラーベ・シェイカー・スルド、ベース、
ガットギターの和音、フルート。2/4 拍子（1 measure＝8 row）で、リズムは2小節周期。"""
from __future__ import annotations

from ..core.composer import RhythmMotif, ScaleRules
from ..core.model import ChordSpec
from ..core.pitch import fold_into_range
from ..profiles.band_common import (
    BandProfile, BassSpec, ChannelDef, CompSpec, LeadSpec, Section, _scale_vol, hits, preset,
)
from ..profiles.registry import register_profile

C = ChordSpec
CH_PERC, CH_BASS, CH_GTR, CH_LEAD = range(4)

# ボサノバのクラーベ（2小節＝16分×16 の 0,3,6 | 10,13）。偶数小節と奇数小節で別の型
CLAVE = ((0, 3, 6), (2, 5))
PERC = hits("surdo", (4,), 44) + hits("shaker", range(8), 16, 0.85)
# ギターの和音（João Gilberto 風のシンコペーション。低音は親指＝ベースのチャンネルが拍を刻む）
GTR = ((0, 3, 6), (2, 4, 6))

LEAD_MOTIFS = {
    "verse": (RhythmMotif((0, 4)), RhythmMotif((0, 3, 6)), RhythmMotif((2, 4, 6))),
    "solo": (RhythmMotif((0, 2, 3, 4, 6)), RhythmMotif((0, 1, 2, 4, 6, 7)), RhythmMotif((1, 3, 4, 6))),
}
BAND = frozenset({"drums", "bass", "comp"})


@register_profile
class BossaNovaProfile(BandProfile):
    id = "bossa-nova"
    display_name = "Bossa Nova"
    description = "ボサノバ。2/4 の柔らかいガットギターと軽いパーカッション"
    description_en = "Bossa nova: soft nylon guitar and light percussion in 2/4"
    title = "Bossa Nova"
    default_filename = "BossaNova.mod"
    tempo_choices = (120, 124, 128, 132, 136, 140)
    rows_per_measure = 8

    KIT = (
        ("rim", preset("drum_rim")), ("shaker", preset("perc_shaker")), ("surdo", preset("perc_surdo")),
        ("bass", preset("bass_finger")), ("flute", preset("wind_flute", volume=38)),
    )
    CHORD_KITS = {"gtr": (preset("gtr_nylon"), 10.0)}
    CHANNELS = (
        ChannelDef("rim/perc", ("rim", "shaker", "surdo"), (("rim", 3), ("surdo", 2))),
        ChannelDef("bass", ("bass",)),
        ChannelDef("guitar", ("gtr",)),
        ChannelDef("flute", ("flute",)),
    )
    DRUM_CHANNEL = {"rim": CH_PERC, "shaker": CH_PERC, "surdo": CH_PERC}
    KEYS = (5, 0, 7, 2)
    MODE_BY_QUALITY = {"m7": "dorian", "dom7": "mixolydian", "m7b5": "locrian"}
    PROGRESSIONS = (
        ("Imaj7-II7-iim7-V7", (C(0, "maj7", label="Imaj7"), C(2, "dom7", label="II7"), C(2, "m7", label="iim7"),
                               C(7, "dom7", label="V7"))),
        ("iim7-V7-Imaj7-VI7", (C(2, "m7", label="iim7"), C(7, "dom7", label="V7"), C(0, "maj7", label="Imaj7"),
                               C(9, "dom7", label="VI7"))),
        ("im7-IV7", (C(0, "m7", label="im7"), C(5, "dom7", label="IV7"))),
        ("iim7b5-V7-im7", (C(2, "m7b5", label="iim7b5"), C(7, "dom7", label="V7"), C(0, "m7", label="im7"),
                           C(0, "m7", label="im7"))),
    )
    SECTIONS = {
        "intro": Section("intro", prog=0, intensity=0.5, parts=frozenset({"bass", "comp"})),
        "a": Section("a", prog=0, intensity=0.7, parts=BAND | {"lead"}),
        "b": Section("b", prog=1, intensity=0.8, parts=BAND | {"lead"}),
        "solo": Section("solo", prog=0, intensity=0.8, parts=BAND | {"lead"}, lead_motifs="solo"),
        "outro": Section("outro", prog=0, intensity=0.5, parts=frozenset({"bass", "comp", "drums"})),
    }
    FORM = ("intro", "a", "a", "b", "a", "solo", "a", "outro")
    GROOVES = {"main": PERC}
    BASS = BassSpec("bass", CH_BASS, kind="bossa", vol=50)
    COMP = CompSpec("gtr", CH_GTR, kind="bossa", vol=40)
    LEAD = LeadSpec("flute", CH_LEAD, ScaleRules(leap_probability=0.2, leap_semitones=(3, 4, 5)), LEAD_MOTIFS,
                    vol=42, gate=0.9, vibrato=0x32)

    def drums(self, mctx, sec, rng, buf):
        super().drums(mctx, sec, rng, buf)
        rim = mctx.instruments["rim"]
        for row in CLAVE[mctx.measure_idx % 2]:
            buf.put(row, CH_PERC, rim.cell(vol=round(40 * (0.6 + 0.4 * sec.intensity))))

    def bass(self, mctx, sec, rng, buf):
        """付点4分＋8分（row 0 に根音、row 6 に5度）。2/4 の1小節で1組。"""
        chord = mctx.chord
        inst = mctx.instruments["bass"]
        fifth = fold_into_range(chord.bass + 7, *self.REGISTERS.bass)
        buf.put(0, CH_BASS, inst.cell(chord.bass, vol=_scale_vol(50, sec)))
        buf.put(6, CH_BASS, inst.cell(fifth, vol=_scale_vol(44, sec)))

    def comp(self, mctx, sec, rng, buf):
        inst = mctx.instruments[self._chord_key("gtr", mctx)]
        for i, row in enumerate(GTR[mctx.measure_idx % 2]):
            buf.put(row, CH_GTR, inst.cell(mctx.chord.harmony, vol=_scale_vol(40 if i == 0 else 34, sec)))
