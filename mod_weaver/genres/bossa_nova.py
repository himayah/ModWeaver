"""bossa-nova（旧 genres/bossa_nova.py の宣言を機械変換したもの。DESIGN.md §6）。"""
from __future__ import annotations

from ..core.composer import RhythmMotif, ScaleRules
from ..core.model import ChordSpec, GmVoice
from ..core.synth_presets import PRESETS
from ..framework.gens import Groove, Layer, Lead, hits
from ..framework.genre import Genre, Harmony, Instrument, Kit, Part, Section
from ..framework.plan import Meter
from ..framework.context import Generator, MeasureCtx
from ..core.pitch import CHORD_QUALITIES, fold_into_range
from ..framework.registry import register_genre

C = ChordSpec


def _inst(key: str, gm: GmVoice, **changes) -> Instrument:
    patch = PRESETS[key]
    if changes:
        import dataclasses
        patch = dataclasses.replace(patch, **changes)
    return Instrument(patch=patch, gm=gm)

GROOVES = {
    "main": hits("surdo", (4,), 44) + hits("shaker", (0, 1, 2, 3, 4, 5, 6, 7), 16, 0.85),
}
LEAD_MOTIFS = {
    "verse": (RhythmMotif(rows=(0, 4)), RhythmMotif(rows=(0, 3, 6)), RhythmMotif(rows=(2, 4, 6))),
    "solo": (RhythmMotif(rows=(0, 2, 3, 4, 6)), RhythmMotif(rows=(0, 1, 2, 4, 6, 7)), RhythmMotif(rows=(1, 3, 4, 6))),
}
METER = Meter(8, 4, (2, 4))
PROGRESSIONS = (
    ("Imaj7-II7-iim7-V7", (C(0, "maj7", label="Imaj7"), C(2, "dom7", label="II7"), C(2, "m7", label="iim7"), C(7, "dom7", label="V7"))),
    ("iim7-V7-Imaj7-VI7", (C(2, "m7", label="iim7"), C(7, "dom7", label="V7"), C(0, "maj7", label="Imaj7"), C(9, "dom7", label="VI7"))),
    ("im7-IV7", (C(0, "m7", label="im7"), C(5, "dom7", label="IV7"))),
    ("iim7b5-V7-im7", (C(2, "m7b5", label="iim7b5"), C(7, "dom7", label="V7"), C(0, "m7", label="im7"), C(0, "m7", label="im7"))),
)


# ボサノバのクラーベ（2小節＝8分×8 の 0,3,6 | 2,5）。偶数小節と奇数小節で別の型
CLAVE = ((0, 3, 6), (2, 5))
# ギターの和音（João Gilberto 風のシンコペーション。低音は親指＝ベースが拍を刻む）
GTR = ((0, 3, 6), (2, 4, 6))


class BossaDrums(Groove):
    """打楽器の型に、クラーベの rim を足す（旧 drums の上書き）。"""

    def measure(self, m: MeasureCtx) -> None:
        super().measure(m)
        for step in CLAVE[m.m.index % 2]:
            if step < m.m.steps:
                m.note(step, "rim", vel=m.scale_drum(40))


class BossaBass(Generator):
    """付点4分＋8分（step 0 に根音、6 に5度）。2/4 の1小節で1組（旧 bass）。"""

    def __init__(self, inst: str, vol: int) -> None:
        self.inst = inst
        self.vol = vol

    def measure(self, m: MeasureCtx) -> None:
        chord = m.m.chord
        fifth = fold_into_range(chord.bass + 7, *m.genre.harmony.registers.bass)
        m.note(0, self.inst, chord.bass, vel=m.scale_vol(self.vol))
        m.note(6, self.inst, fifth, vel=m.scale_vol(44))


class BossaComp(Generator):
    """ガットギターの和音（シンコペーション。旧 comp）。"""

    def __init__(self, inst: str, vol: int, strum_ms: float) -> None:
        self.inst = inst
        self.vol = vol
        self.strum_ms = strum_ms

    def measure(self, m: MeasureCtx) -> None:
        for i, step in enumerate(GTR[m.m.index % 2]):
            m.note(step, self.inst, m.m.chord.harmony, vel=m.scale_vol(40 if i == 0 else 34),
                   chord=CHORD_QUALITIES[m.m.quality], strum_ms=self.strum_ms)


@register_genre
class BossaNovaGenre(Genre):
    id = "bossa-nova"
    display_name = "Bossa Nova"
    description = "ボサノバ。2/4 の柔らかいガットギターと軽いパーカッション"
    description_en = "Bossa nova: soft nylon guitar and light percussion in 2/4"
    title = "Bossa Nova"
    tempo_choices = (120, 124, 128, 132, 136, 140)

    instruments = {
        "rim": _inst("drum_rim", GmVoice(drum_note=37)),
        "shaker": _inst("perc_shaker", GmVoice(drum_note=70)),
        "surdo": _inst("perc_surdo", GmVoice(drum_note=35)),
        "bass": _inst("bass_finger", GmVoice(program=33)),
        "flute": _inst("wind_flute", GmVoice(program=73), volume=38),
        "ep": _inst("keys_ep", GmVoice(program=4), volume=34),
        "gtr": _inst("gtr_nylon", GmVoice(program=24)),
    }
    harmony = Harmony(keys=(5, 0, 7, 2), mode="ionian", mode_by_quality={"m7": "dorian", "dom7": "mixolydian", "m7b5": "locrian"}, progressions=PROGRESSIONS, n_progressions=2)
    sections = {
        "intro": Section(intensity=0.5, parts=frozenset({"bass", "comp"}), meter=METER, measures=8),
        "a": Section(intensity=0.7, parts=frozenset({"lead", "bass", "drums", "comp"}), meter=METER, measures=8),
        "b": Section(prog=1, intensity=0.8, parts=frozenset({"lead", "bass", "drums", "comp"}), meter=METER, measures=8),
        "solo": Section(intensity=0.8, parts=frozenset({"lead", "bass", "drums", "comp"}), motifs="solo", meter=METER, measures=8),
        "outro": Section(intensity=0.5, parts=frozenset({"bass", "drums", "comp"}), meter=METER, measures=8),
    }
    form = ("intro", "a", "a", "b", "a", "solo", "a", "outro")
    parts = (
        Part("drums", BossaDrums(GROOVES), pan=128,
             kit=Kit(groups=(("rim/surdo", ("rim", "surdo")), ("shaker", ("shaker",))),
                     priority={"rim": 3, "surdo": 2},
                     single_priority={"rim": 3, "surdo": 2, "shaker": 1},
                     group_pan={"shaker": 164})),
        Part("bass", BossaBass("bass", vol=50), pan=128),
        Part("comp", BossaComp("gtr", vol=40, strum_ms=10.0), pan=84),
        Part("lead", Lead("flute", ScaleRules(leap_probability=0.2, leap_semitones=(3, 4, 5)), LEAD_MOTIFS,
                   vol=42, gate=0.9, vibrato=0x32), pan=172),
        Part("e.piano", Layer("ep", vol=26, register=(19, 31)), follow="lead", pan=100, min_channels=6),
    )
    mod_channels = {4: 2, 6: 1}
