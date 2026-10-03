"""russian-folk（ロシア民謡風。NEW_GENRES_DESIGN.md §8）。

系統は seed で選ぶ: ``lyric``（叙情歌。3/4・ゆっくり）と ``dance``（舞曲。2/4・主題を変奏するたびに加速する）。
バラライカのトレモロの旋律・バヤンの「オン・パッ」・和声的短音階。旋律は手続き的に作る（実在の民謡は使わない）。
"""
from __future__ import annotations

import dataclasses
import random

from ..core.composer import RhythmMotif, ScaleRules
from ..core.model import ChordSpec, GmVoice
from ..core.pitch import CHORD_QUALITIES, fold_into_range
from ..framework.context import Generator, MeasureCtx
from ..framework.gens import Groove, Pad, hits
from ..framework.genre import Genre, Harmony, Kit, Part, Section
from ..framework.plan import Meter, SongPlan, default_plan
from ..framework.registry import register_genre
from ._ornament import Heterophony, OrnamentedLead, WithTempo, inst as _inst, retime

C = ChordSpec

LYRIC = Meter(12, 4, (3, 4))
DANCE = Meter(8, 4, (2, 4))
FAMILIES = {                                  # 名前: (表示, 拍子, テンポの候補, 曲の並び)
    "lyric": ("Lyric song 3/4", LYRIC, (66, 70, 74, 78, 84),
              ("intro", "theme", "theme2", "theme", "outro")),
    "dance": ("Dance 2/4 (accelerating variations)", DANCE, (118, 124, 130, 136, 142),
              ("intro", "theme", "theme2", "theme", "var1", "var1", "var2", "var2", "var3", "var3", "outro")),
}
# 舞曲は変奏ごとに開始 BPM の倍率で加速する（区間名 -> (開始, 終了)）
DANCE_TEMPO = {"intro": (1.0, 1.0), "theme": (1.0, 1.0), "theme2": (1.0, 1.0), "var1": (1.06, 1.06),
               "var2": (1.12, 1.12), "var3": (1.2, 1.2), "outro": (1.2, 1.1)}
LYRIC_TEMPO = {"outro": (1.0, 0.85)}

GROOVES = {
    "lyric:main": hits("stomp", (0,), 40) + hits("tamb", (4, 8), 26),
    "dance:main": hits("stomp", (0, 4), 52) + hits("tamb", (0, 2, 4, 6), 24, 0.85),
}
LEAD_MOTIFS = {
    "lyric:theme": (RhythmMotif(rows=(0, 6, 8)), RhythmMotif(rows=(0, 4, 6, 8, 10)), RhythmMotif(rows=(0, 8))),
    "dance:theme": (RhythmMotif(rows=(0, 2, 4, 6)), RhythmMotif(rows=(0, 2, 3, 4, 6)), RhythmMotif(rows=(0, 4, 6))),
    "dance:var1": (RhythmMotif(rows=(0, 2, 4, 6)), RhythmMotif(rows=(0, 2, 4, 5, 6, 7))),
    "dance:var2": (RhythmMotif(rows=(0, 1, 2, 3, 4, 6)), RhythmMotif(rows=(0, 2, 3, 4, 5, 6))),
    "dance:var3": (RhythmMotif(rows=(0, 1, 2, 3, 4, 5, 6, 7)), RhythmMotif(rows=(0, 1, 2, 3, 4, 5, 6))),
}
PROGRESSIONS = (
    ("i-iv-V7-i", (C(0, "min", label="i"), C(5, "min", label="iv"), C(7, "dom7", label="V7"), C(0, "min", label="i"))),
    ("i-VII-VI-V", (C(0, "min", label="i"), C(10, "maj", label="VII"), C(8, "maj", label="VI"), C(7, "maj", label="V"))),
    ("i-III-VII-i", (C(0, "min", label="i"), C(3, "maj", label="III"), C(10, "maj", label="VII"), C(0, "min", label="i"))),
    ("i-iv-i-V7", (C(0, "min", label="i"), C(5, "min", label="iv"), C(0, "min", label="i"), C(7, "dom7", label="V7"))),
)


class OomPah(Generator):
    """バヤンのオン・パッ。パッ（和音）の位置は 3/4 が拍 2・3、2/4 が拍 2（変奏が進むと裏拍も足す）。"""

    def measure(self, m: MeasureCtx) -> None:
        lyric = m.song.extra["family"] == "lyric"
        steps = (4, 8) if lyric else (4,)
        if "busy" in m.plan.section.tags:
            steps = (2, 4, 6)
        chord = CHORD_QUALITIES[m.m.quality]
        for i, step in enumerate(steps):
            if step < m.m.steps:
                m.note(step, "bayan", m.m.chord.harmony, vel=m.scale_vol(34 if i == 0 else 28), chord=chord,
                       dur=max(1, 3))


class RuBass(Generator):
    """根音（拍1）と、舞曲では拍2に5度。"""

    def measure(self, m: MeasureCtx) -> None:
        bass = m.genre.harmony.registers.bass
        m.note(0, "bass", m.m.chord.bass, vel=m.scale_vol(50))
        if m.song.extra["family"] == "dance":
            m.note(4, "bass", fold_into_range(m.m.chord.bass + 7, *bass), vel=m.scale_vol(42))


def _sec(parts, *, prog=0, intensity=0.8, measures=8, motifs="theme", tags=()) -> Section:
    return Section(prog=prog, measures=measures, intensity=intensity, parts=frozenset(parts), motifs=motifs,
                   tags=frozenset(tags))


@register_genre
class RussianFolkGenre(Genre):
    id = "russian-folk"
    category = "genre"
    display_name = "Russian Folk Style"
    description = "ロシア民謡風。バラライカのトレモロとバヤンのオン・パッ、和声的短音階。叙情歌と加速する舞曲（実在の民謡は使わない）"
    description_en = "Russian folk style: balalaika tremolo, bayan oom-pah, harmonic minor; a lyric song or an accelerating dance"
    title = "Russian Folk"
    tempo_choices = tuple(sorted({b for f in FAMILIES.values() for b in f[2]}))

    instruments = {
        "stomp": _inst("perc_stomp", GmVoice(drum_note=35)),
        "tamb": _inst("perc_tambourine", GmVoice(drum_note=54)),
        "bass": _inst("bass_finger", GmVoice(program=33)),
        "bayan": _inst("ru_bayan", GmVoice(program=21)),
        "balalaika": _inst("ru_balalaika", GmVoice(program=105)),
        "domra": _inst("ru_balalaika", GmVoice(program=105), name="Domra", volume=36),
        "choir": _inst("vox_choir", GmVoice(program=52), volume=26),
    }
    harmony = Harmony(keys=(9, 2, 4, 7), mode="harmonic_minor", progressions=PROGRESSIONS, n_progressions=2)
    _core = {"drums", "bass", "bayan", "lead"}
    sections = {
        "intro": _sec({"bayan", "bass"}, intensity=0.5, measures=4),
        "theme": _sec(_core, intensity=0.7),
        "theme2": _sec(_core | {"choir"}, prog=1, intensity=0.8),
        "var1": _sec(_core, intensity=0.85, motifs="var1"),
        "var2": _sec(_core | {"choir"}, prog=1, intensity=0.95, motifs="var2", tags=("busy",)),
        "var3": _sec(_core | {"choir"}, intensity=1.0, motifs="var3", tags=("busy",)),
        "outro": _sec({"drums", "bass", "bayan", "lead"}, intensity=0.6, measures=4),
    }
    form = FAMILIES["dance"][3]
    parts = (
        Part("drums", WithTempo(Groove(GROOVES, groove_name=lambda sp: f"{sp.extra['family']}:{sp.section.groove}"),
                                lambda sp: (DANCE_TEMPO if sp.extra["family"] == "dance" else LYRIC_TEMPO)
                                .get(sp.name, (1.0, 1.0))), pan=128,
             kit=Kit(groups=(("stomp", ("stomp",)), ("tambourine", ("tamb",))),
                     priority={"stomp": 2, "tamb": 1}, single_priority={"stomp": 2, "tamb": 1},
                     group_pan={"tambourine": 168})),
        Part("bass", RuBass(), pan=128),
        Part("bayan", OomPah(), pan=88),
        Part("lead", OrnamentedLead("balalaika", ScaleRules(leap_probability=0.1, leap_semitones=(3, 4, 5)), LEAD_MOTIFS,
                                    vol=46, gate=1.0, tremolo=2), pan=172),
        Part("domra", Heterophony("domra", delay=0, drop=0.25, shift=-12, vol_ratio=0.6, lo=12, hi=35),
             follow="lead", pan=100, min_channels=6),
        Part("choir", Pad("choir", vol=26), pan=128, min_channels=8),
    )
    mod_channels = {4: 1, 6: 2, 8: 1}

    def plan(self, rng: random.Random) -> SongPlan:
        family = rng.choice(list(FAMILIES))
        base = default_plan(self, rng)
        label, meter, bpms, order = FAMILIES[family]
        base.bpm = rng.choice(bpms)
        base.summary = [f"Rhythm      : {label}", *base.summary]
        base.extra = dict(base.extra, family=family)
        base.order = list(order)
        for name in [n for n in base.sections if n not in order]:
            del base.sections[name]
        for sp in base.sections.values():
            retime(sp, meter)
            sp.section = dataclasses.replace(sp.section, motifs=f"{family}:{sp.section.motifs}")
            sp.extra = dict(sp.extra, family=family)
        return base
