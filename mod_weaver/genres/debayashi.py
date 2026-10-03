"""debayashi（出囃子風。NEW_GENRES_DESIGN.md §14.7）。

2/4・都節音階・和音なし（主音の持続だけ）。三味線の旋律（撥の前打音・すり＝グリッサンド）、締太鼓・大太鼓・当たり鉦、
能管風の笛（導入の「ヒシギ」＝上昇音と、旋律への異種同音）。繰り返しごとに加速する。
実在の出囃子・囃子方の旋律・掛け声は使わない。
"""
from __future__ import annotations

from ..core.composer import RhythmMotif, ScaleRules
from ..core.model import ChordSpec, GmVoice
from ..core.pitch import fold_into_range
from ..framework.context import Generator, MeasureCtx
from ..framework.gens import Groove, hits
from ..framework.genre import Genre, Harmony, Kit, Part, Section
from ..framework.plan import Meter
from ..framework.registry import register_genre
from ..framework.score import Glide
from ._ornament import Heterophony, OrnamentedLead, WithTempo, inst as _inst

C = ChordSpec

METER = Meter(8, 4, (2, 4))
TEMPO = {"intro": (1.0, 1.0), "a1": (1.0, 1.0), "a2": (1.1, 1.1), "a3": (1.22, 1.22), "outro": (1.22, 1.22)}
GROOVES = {
    "main": hits("shime", (0, 4), 46) + hits("shime", (2, 6), 32) + hits("shime", (1, 3, 5, 7), 16, 0.5)
            + hits("odaiko", (0,), 52) + hits("kane", (0, 4), 30) + hits("kane", (2, 6), 22, 0.6),
    "intro": hits("shime", (0, 4), 36) + hits("odaiko", (0,), 44),
}
LEAD_MOTIFS = {
    "verse": (RhythmMotif(rows=(0, 2, 3, 4, 6)), RhythmMotif(rows=(0, 1, 2, 4, 6)), RhythmMotif(rows=(0, 2, 4, 5, 6))),
}
PROGRESSIONS = (("tonic drone", (C(0, "sus4", label="I"),)),)


class Hishigi(Generator):
    """笛の「ヒシギ」: 低い音から高い音へ駆け上がる（区間の最初の小節）。"""

    def measure(self, m: MeasureCtx) -> None:
        if not m.is_first:
            return
        low = fold_into_range(m.plan.tonic, 17, 28)
        m.note(0, "nokan", low, vel=m.scale_vol(36), dur=None)
        m.note(3, "nokan", low + 7, vel=m.scale_vol(44), dur=None, arts=(Glide(steps=4),))


def _sec(parts, *, intensity=0.8, measures=8, groove="main", kind="") -> Section:
    return Section(measures=measures, intensity=intensity, parts=frozenset(parts), groove=groove, meter=METER, kind=kind)


@register_genre
class DebayashiGenre(Genre):
    id = "debayashi"
    category = "style"
    display_name = "Debayashi Style"
    description = "出囃子風。都節音階・和音なし、三味線と太鼓と当たり鉦、笛のヒシギ、繰り返すたびに加速（実在の曲・掛け声は使わない）"
    description_en = "Debayashi (entrance music) style: miyako-bushi scale without chords, shamisen, drums, gong and flute hishigi, speeding up on each repeat"
    title = "Debayashi"
    tempo_choices = (110, 116, 122, 128, 134, 140)

    instruments = {
        "shime": _inst("jp_shime", GmVoice(drum_note=38)),
        "odaiko": _inst("perc_taiko", GmVoice(drum_note=41)),
        "kane": _inst("jp_kane", GmVoice(drum_note=56)),
        "shamisen": _inst("jp_shamisen", GmVoice(program=106)),
        "nokan": _inst("jp_ryuteki", GmVoice(program=77), volume=40),
        "nokan_h": _inst("jp_ryuteki", GmVoice(program=77), name="NokanH", volume=32),
    }
    harmony = Harmony(keys=(2, 9, 4, 7), mode="miyakobushi", progressions=PROGRESSIONS, n_progressions=1)
    sections = {
        "intro": _sec({"drums", "hishigi"}, intensity=0.5, measures=4, groove="intro"),
        "a1": _sec({"drums", "lead", "nokan"}, intensity=0.75, kind="a"),
        "a2": _sec({"drums", "lead", "nokan"}, intensity=0.9, kind="a"),
        "a3": _sec({"drums", "lead", "nokan"}, intensity=1.0, kind="a"),
        "outro": _sec({"drums", "lead", "hishigi"}, intensity=0.6, measures=4),
    }
    form = ("intro", "a1", "a2", "a3", "outro")
    parts = (
        Part("drums", Groove(GROOVES), pan=128,
             kit=Kit(groups=(("shime", ("shime",)), ("odaiko", ("odaiko",)), ("kane", ("kane",))),
                     priority={"odaiko": 3, "shime": 2, "kane": 1},
                     single_priority={"odaiko": 3, "shime": 2, "kane": 1}, group_pan={"kane": 176})),
        Part("lead", WithTempo(OrnamentedLead("shamisen", ScaleRules(leap_probability=0.1, leap_semitones=(4, 5, 7)),
                                              LEAD_MOTIFS, vol=46, gate=0.7, grace=0.5, scoop=0.3, scoop_semitones=2.0),
                               lambda sp: TEMPO[sp.name]), pan=110),
        Part("hishigi", Hishigi(), pan=160),
        Part("nokan", Heterophony("nokan_h", delay=0, drop=0.4, shift=0, vol_ratio=0.7, lo=12, hi=35, min_dur=1),
             follow="lead", pan=150, min_channels=6),
    )
    mod_channels = {4: 1, 6: 2}
