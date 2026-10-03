"""acoustic-ssw（旧 genres/acoustic_ssw.py の宣言を機械変換したもの。DESIGN.md §6）。"""
from __future__ import annotations

from ..core.composer import RhythmMotif, ScaleRules
from ..core.model import ChordSpec, GmVoice
from ..core.synth_presets import PRESETS
from ..framework.gens import BassLine, Echo, Groove, Lead, hits
from ..framework.genre import Genre, Harmony, Instrument, Kit, Part, Section
from ..framework.context import Generator, MeasureCtx
from ..core.pitch import fold_into_range
from ..framework.gens._common import arp_tones
from ..framework.registry import register_genre

C = ChordSpec


def _inst(key: str, gm: GmVoice, **changes) -> Instrument:
    patch = PRESETS[key]
    if changes:
        import dataclasses
        patch = dataclasses.replace(patch, **changes)
    return Instrument(patch=patch, gm=gm)

GROOVES = {
    "main": hits("low", (0, 10), 44) + hits("slap", (4, 12), 38) + hits("shaker", (2, 6, 10, 14), 18, 0.8),
}
LEAD_MOTIFS = {
    "verse": (RhythmMotif(rows=(0, 2, 4, 8)), RhythmMotif(rows=(0, 4, 6, 8)), RhythmMotif(rows=(2, 4, 6, 10))),
    "chorus": (RhythmMotif(rows=(0, 4, 8, 10)), RhythmMotif(rows=(0, 2, 4, 6, 8)), RhythmMotif(rows=(0, 6, 8, 10))),
}
PROGRESSIONS = (
    ("I-V-vi-IV", (C(0, "maj", label="I"), C(7, "maj", label="V"), C(9, "min", label="vi"), C(5, "maj", label="IV"))),
    ("vi-IV-I-V", (C(9, "min", label="vi"), C(5, "maj", label="IV"), C(0, "maj", label="I"), C(7, "maj", label="V"))),
    ("I-iii-vi-IV", (C(0, "maj", label="I"), C(4, "min", label="iii"), C(9, "min", label="vi"), C(5, "maj", label="IV"))),
)


THUMB_REGISTER = (5, 19)                       # 親指（根音と5度）
FINGER_REGISTER = (17, 29)                     # 他の指（上声）


class Travis(Generator):
    """トラヴィス奏法: 親指が4分で根音と5度を交互に、他の指が8分裏で上声を弾く（旧 comp の上書き）。"""

    def __init__(self, inst: str, vol: int = 40) -> None:
        self.inst = inst
        self.vol = vol

    def measure(self, m: MeasureCtx) -> None:
        chord = m.m.chord
        root = fold_into_range(chord.bass, *THUMB_REGISTER)
        fifth = fold_into_range(chord.bass + 7, *THUMB_REGISTER)
        upper = [t for t in arp_tones(chord, FINGER_REGISTER) if t % 12 != chord.bass % 12] or [chord.harmony + 12]
        vol = m.scale_vol(self.vol)
        for beat in range(4):
            if beat * 4 + 2 >= m.m.steps:
                break
            m.note(beat * 4, self.inst, root if beat % 2 == 0 else fifth, vel=vol)
            m.note(beat * 4 + 2, self.inst, upper[(beat + m.m.index) % len(upper)], vel=max(1, vol - 8))


@register_genre
class AcousticSswGenre(Genre):
    id = "acoustic-ssw"
    category = "style"
    display_name = "Acoustic Singer-songwriter"
    description = "弾き語り風。指弾きのギターと軽いパーカッション、歌のような旋律"
    description_en = "Acoustic singer-songwriter style: fingerpicked guitar, light percussion and a vocal-like melody"
    title = "Acoustic Diary"
    tempo_choices = (80, 84, 88, 92, 96, 100)

    instruments = {
        "low": _inst("perc_cajon", GmVoice(drum_note=36)),
        "slap": _inst("perc_cajon_slap", GmVoice(drum_note=38)),
        "shaker": _inst("perc_shaker", GmVoice(drum_note=70)),
        "bass": _inst("bass_finger", GmVoice(program=33)),
        "gtr": _inst("gtr_acoustic", GmVoice(program=25)),
        "vox": _inst("vox_ooh", GmVoice(program=53)),
    }
    harmony = Harmony(keys=(7, 0, 2, 4), mode="ionian", progressions=PROGRESSIONS, n_progressions=2)
    sections = {
        "intro": Section(intensity=0.5, parts=frozenset({"comp"})),
        "verse": Section(intensity=0.6, parts=frozenset({"lead", "bass", "drums", "comp"})),
        "chorus": Section(prog=1, intensity=0.85, parts=frozenset({"lead", "bass", "drums", "comp"}), motifs="chorus"),
        "bridge": Section(prog=2, intensity=0.7, parts=frozenset({"lead", "bass", "comp"})),
        "outro": Section(intensity=0.45, parts=frozenset({"comp"})),
    }
    form = ("intro", "verse", "chorus", "verse", "chorus", "bridge", "chorus", "outro")
    parts = (
        Part("drums", Groove(GROOVES), pan=128,
             kit=Kit(groups=(("cajon", ("low", "slap")), ("shaker", ("shaker",))),
                     priority={"slap": 3, "low": 2},
                     single_priority={"low": 2, "slap": 3, "shaker": 1},
                     group_pan={"shaker": 164})),
        Part("bass", BassLine("bass", kind="whole", vol=38), pan=128),
        Part("comp", Travis("gtr", vol=40), pan=84),
        Part("lead", Lead("vox", ScaleRules(leap_probability=0.15, leap_semitones=(3, 4, 5)), LEAD_MOTIFS,
                   vol=44, gate=0.85, vibrato=0x22), pan=172),
        Part("voice echo", Echo(delay=3, ratio=0.45), follow="lead", pan=100, min_channels=6),
    )
    mod_channels = {4: 2, 6: 1}
