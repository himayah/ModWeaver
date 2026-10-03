"""flamenco（フラメンコ風）。系統は seed で選ぶ: ``solea``（12拍のコンパス。強勢は 3・6・8・10・12 拍）と ``rumba``（4/4）。

フリギア・ドミナント（アンダルシア進行 iv–III–II–I）、ラスゲアード（和音のかき鳴らし）、パルマ・カホン・サパテアード、
ファルセータ（ギターの旋律。前打音・ロール）。
"""
from __future__ import annotations

import dataclasses
import random

from ..core.composer import RhythmMotif, ScaleRules
from ..core.model import ChordSpec, GmVoice
from ..core.pitch import CHORD_QUALITIES
from ..framework.context import Generator, MeasureCtx
from ..framework.gens import BassLine, Groove, hits
from ..framework.genre import Genre, Harmony, Kit, Part, Section
from ..framework.plan import Meter, SongPlan, default_plan
from ..framework.registry import register_genre
from ._ornament import Heterophony, OrnamentedLead, WithTempo, inst as _inst, retime

C = ChordSpec

SOLEA = Meter(24, 2, (12, 8))                  # 1 step ＝ 半拍。12拍＝24 step。BPM は1拍の数
RUMBA = Meter(16, 4)
FAMILIES = {                                    # 名前: (表示, 拍子, テンポの候補, 曲の並び)
    "solea": ("Solea (12-beat compas)", SOLEA, (96, 100, 104, 110), ("intro", "a", "b", "a", "outro")),
    "rumba": ("Rumba flamenca (4/4)", RUMBA, (104, 110, 116, 122), ("intro", "a", "a", "b", "b", "a", "outro")),
}
ACCENT = {"solea": (4, 10, 14, 18, 22), "rumba": (4, 12)}                 # パルマの位置
RASGUEADO = {"solea": ((0, 46), (4, 40), (10, 44), (14, 40), (18, 44), (22, 40)),
             "rumba": ((0, 46), (4, 36), (6, 40), (8, 44), (12, 36), (14, 40))}
GROOVES = {
    "solea:main": hits("cajon_lo", (0, 10), 50) + hits("cajon_slap", (4, 14, 22), 40) + hits("clap", (4, 10, 14, 18, 22), 34, 0.9),
    "solea:intense": hits("cajon_lo", (0, 10), 54) + hits("cajon_slap", (4, 14, 22), 44) + hits("clap", (4, 10, 14, 18, 22), 38)
                     + hits("stomp", (4, 10, 14, 18, 22), 40),
    "rumba:main": hits("cajon_lo", (0, 8), 50) + hits("cajon_slap", (4, 12), 42) + hits("clap", (4, 12), 34)
                  + hits("cajon_slap", (6, 14), 26, 0.7),
    "rumba:intense": hits("cajon_lo", (0, 8), 54) + hits("cajon_slap", (4, 12), 46) + hits("clap", (2, 4, 6, 10, 12, 14), 36)
                     + hits("stomp", (0, 8), 40),
}
LEAD_MOTIFS = {
    "solea:verse": (RhythmMotif(rows=(0, 4, 10, 14, 18)), RhythmMotif(rows=(0, 2, 4, 6, 10, 14, 18, 22)),
                    RhythmMotif(rows=(0, 4, 8, 10, 14, 16, 20))),
    "rumba:verse": (RhythmMotif(rows=(0, 2, 4, 6, 8, 10, 12)), RhythmMotif(rows=(0, 3, 4, 6, 8, 12, 14)),
                    RhythmMotif(rows=(0, 4, 6, 8, 12))),
}
PROGRESSIONS = (
    ("Andalusian iv-III-II-I", (C(5, "min", label="iv"), C(3, "maj", label="III"), C(1, "maj", label="II"), C(0, "maj", label="I"))),
    ("I-bII-I-bII", (C(0, "maj", label="I"), C(1, "maj", label="bII"), C(0, "maj", label="I"), C(1, "maj", label="bII"))),
    ("I-bII-bIII-bII", (C(0, "maj", label="I"), C(1, "maj", label="bII"), C(3, "maj", label="bIII"), C(1, "maj", label="bII"))),
)


class Rasgueado(Generator):
    """ギターのかき鳴らし（和音。コンパスの強勢の位置）。"""

    inst = "gtr"

    def measure(self, m: MeasureCtx) -> None:
        shape = CHORD_QUALITIES[m.m.quality]
        for step, vol in RASGUEADO[m.song.extra["family"]]:
            if step < m.m.steps:
                m.note(step, "gtr", m.m.chord.harmony, vel=m.scale_vol(vol), chord=shape, strum_ms=8.0, dur=3)


def _sec(parts, *, prog=0, intensity=0.8, measures=4, groove="main") -> Section:
    return Section(prog=prog, measures=measures, intensity=intensity, parts=frozenset(parts), groove=groove)


@register_genre
class FlamencoGenre(Genre):
    id = "flamenco"
    category = "genre"
    display_name = "Flamenco"
    description = "フラメンコ風。フリギア・ドミナントとアンダルシア進行、ラスゲアード、パルマとカホン、12拍のコンパスか4/4のルンバ"
    description_en = "Flamenco style: phrygian dominant with the Andalusian cadence, rasgueado, palmas and cajon, a 12-beat compas or 4/4 rumba"
    title = "Flamenco Compas"
    tempo_choices = tuple(sorted({b for f in FAMILIES.values() for b in f[2]}))

    instruments = {
        "cajon_lo": _inst("perc_cajon", GmVoice(drum_note=41)),
        "cajon_slap": _inst("perc_cajon_slap", GmVoice(drum_note=39)),
        "clap": _inst("fb_clap", GmVoice(drum_note=39)),
        "stomp": _inst("perc_stomp", GmVoice(drum_note=35)),
        "bass": _inst("bass_finger", GmVoice(program=33), volume=46),
        "gtr": _inst("gtr_nylon", GmVoice(program=24), volume=44),
        "falseta": _inst("gtr_nylon", GmVoice(program=24), name="Falseta", volume=46),
        "gtr2": _inst("gtr_nylon", GmVoice(program=24), name="Guitar2", volume=34),
    }
    harmony = Harmony(keys=(4, 9, 2, 11), mode="phrygian_dominant", progressions=PROGRESSIONS, n_progressions=2)
    sections = {
        "intro": _sec({"lead", "comp"}, intensity=0.55),
        "a": _sec({"lead", "comp", "drums", "bass"}, intensity=0.8),
        "b": _sec({"lead", "comp", "drums", "bass"}, prog=1, intensity=1.0, groove="intense"),
        "outro": _sec({"lead", "comp", "drums"}, intensity=0.6),
    }
    form = ("intro", "a", "b", "outro")
    parts = (
        Part("drums", Groove(GROOVES, groove_name=lambda sp: f"{sp.extra['family']}:{sp.section.groove}"), pan=128,
             kit=Kit(groups=(("cajon", ("cajon_lo", "cajon_slap")), ("palmas", ("clap",)), ("stomp", ("stomp",))),
                     priority={"cajon_lo": 3, "cajon_slap": 2}, single_priority={"cajon_lo": 3, "cajon_slap": 2, "clap": 1, "stomp": 2},
                     group_pan={"palmas": 164, "stomp": 92})),
        Part("bass", BassLine("bass", kind="rootfifth", vol=44), pan=128, min_channels=6),
        Part("comp", WithTempo(Rasgueado(), lambda sp: (1.0, 1.15) if sp.name == "b" and sp.extra["family"] == "solea"
                               else (1.0, 1.0)), pan=84),
        Part("lead", OrnamentedLead("falseta", ScaleRules(leap_probability=0.12, leap_semitones=(3, 4, 5)), LEAD_MOTIFS,
                                    vol=46, gate=0.85, grace=0.35, roll=0.3), pan=172),
        Part("gtr2", Heterophony("gtr2", delay=2, drop=0.3, shift=-12, vol_ratio=0.7, lo=0, hi=35, min_dur=1),
             follow="lead", pan=100, min_channels=6),
    )
    mod_channels = {4: 1, 6: 2}

    def plan(self, rng: random.Random) -> SongPlan:
        family = rng.choice(list(FAMILIES))
        base = default_plan(self, rng)
        label, meter, bpms, order = FAMILIES[family]
        base.bpm = rng.choice(bpms)
        base.summary = [f"Rhythm      : {label}", *base.summary]
        base.extra = dict(base.extra, family=family)
        base.order = list(order)
        for sp in base.sections.values():
            retime(sp, meter)
            sp.section = dataclasses.replace(sp.section, motifs=f"{family}:{sp.section.motifs}")
            sp.extra = dict(sp.extra, family=family)
        return base
