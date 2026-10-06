"""okinawan（沖縄民謡風。NEW_GENRES_DESIGN.md §5）。

琉球音階と三線風の撥弦の旋律＋笛の異種同音。系統は seed で選ぶ: ``shima``（島唄。ゆったり）と
``kachashi``（カチャーシー。速く、8分が 2:1 にハネる）。実在の曲・歌詞は使わない。
"""
from __future__ import annotations

import dataclasses
import random

from ..core.composer import RhythmMotif, ScaleRules
from ..core.model import ChordSpec, GmVoice
from ..framework.gens import BassLine, Comp, Groove, Pad, Sing, hits
from ..framework.genre import Genre, Harmony, Kit, Part, Section, Voice
from ..framework.plan import Meter, SongPlan, Swing, default_plan
from ..framework.registry import register_genre
from ._ornament import Heterophony, OrnamentedLead, WithTempo, inst as _inst, retime

C = ChordSpec

SHIMA = Meter(16, 4)
KACHASHI = Meter(8, 2)                       # 8分の格子。Swing(16, 8) で 2:1 にハネる
FAMILIES = {                                 # 名前: (表示, 拍子, スウィング, テンポの候補, 曲の並び)
    "shima": ("Shima-uta (slow)", SHIMA, None, (76, 80, 84, 88, 92),
              ("intro", "a", "a", "b", "a", "outro")),
    "kachashi": ("Kachashi (fast, swung)", KACHASHI, Swing(16, 8), (130, 138, 146, 154),
                 ("intro", "a", "a", "b", "b", "c", "c", "outro")),
}
KACHASHI_TEMPO = {"b": (1.05, 1.05), "c": (1.12, 1.12), "outro": (1.12, 0.95)}

GROOVES = {
    "shima:main": hits("paran", (0, 8), 40) + hits("sanba", (4, 12), 28, 0.8),
    "kachashi:main": hits("paran", (0, 2, 4, 6), 46) + hits("sanba", (1, 3, 5, 7), 34, 0.9) + hits("stomp", (0, 4), 36),
}
LEAD_MOTIFS = {
    "shima:verse": (RhythmMotif(rows=(0, 6, 8, 12)), RhythmMotif(rows=(0, 4, 8)), RhythmMotif(rows=(0, 3, 6, 8, 12))),
    "kachashi:verse": (RhythmMotif(rows=(0, 2, 4, 6)), RhythmMotif(rows=(0, 1, 2, 4, 6)), RhythmMotif(rows=(0, 2, 3, 4, 6))),
}
PROGRESSIONS = (
    ("I-IV-V-I", (C(0, "maj", label="I"), C(5, "maj", label="IV"), C(7, "maj", label="V"), C(0, "maj", label="I"))),
    ("I-IV-I-V", (C(0, "maj", label="I"), C(5, "maj", label="IV"), C(0, "maj", label="I"), C(7, "maj", label="V"))),
    ("I-V-IV-I", (C(0, "maj", label="I"), C(7, "maj", label="V"), C(5, "maj", label="IV"), C(0, "maj", label="I"))),
)


def _sec(parts, *, prog=0, intensity=0.8, measures=8) -> Section:
    return Section(prog=prog, measures=measures, intensity=intensity, parts=frozenset(parts))


@register_genre
class OkinawanGenre(Genre):
    id = "okinawan"
    category = "style"
    display_name = "Okinawan Folk Style"
    description = "沖縄民謡風。琉球音階、三線風の撥弦と笛、ゆったりした島唄と速くハネるカチャーシー（実在の曲・歌詞は使わない）"
    description_en = "Okinawan folk style: Ryukyu scale, sanshin-like plucked strings and flute, a slow shima-uta or a swung kachashi dance"
    title = "Okinawan Folk"
    tempo_choices = tuple(sorted({b for f in FAMILIES.values() for b in f[3]}))

    instruments = {
        "paran": _inst("oki_parankuu", GmVoice(drum_note=60)),
        "sanba": _inst("oki_sanba", GmVoice(drum_note=75)),
        "stomp": _inst("perc_stomp", GmVoice(drum_note=35)),
        "bass": _inst("bass_finger", GmVoice(program=33)),
        "sanshin": _inst("oki_sanshin", GmVoice(program=106), volume=46),
        "sanshin_bk": _inst("oki_sanshin", GmVoice(program=106), name="SanshinBk", volume=34),
        "fue": _inst("wind_flute", GmVoice(program=77), name="Fue", volume=32),
        "chorus": _inst("vox_ooh", GmVoice(program=53), volume=24),
        "voice": Voice(GmVoice(program=54), timbre="female", volume=46),     # --voice で歌う（旋律は lead と同じ）
    }
    harmony = Harmony(keys=(0, 5, 7), mode="ryukyu", progressions=PROGRESSIONS, n_progressions=2)
    _core = {"drums", "bass", "lead"}
    sections = {
        "intro": _sec({"lead", "bass"}, intensity=0.5, measures=4),
        "a": _sec(_core | {"comp", "vocal"}, intensity=0.7),
        "b": _sec(_core | {"comp", "chorus", "vocal"}, prog=1, intensity=0.85),
        "c": _sec(_core | {"comp", "chorus", "vocal"}, intensity=1.0),
        "outro": _sec({"lead", "bass", "drums"}, intensity=0.5, measures=4),
    }
    form = ("intro", "a", "b", "c", "outro")     # 全系統の区間の和集合（曲の並びは plan() が系統ごとに決める）
    parts = (
        Part("drums", WithTempo(Groove(GROOVES, groove_name=lambda sp: f"{sp.extra['family']}:{sp.section.groove}"),
                                lambda sp: KACHASHI_TEMPO.get(sp.name, (1.0, 1.0)) if sp.extra["family"] == "kachashi"
                                else None), pan=128,
             kit=Kit(groups=(("paran/stomp", ("paran", "stomp")), ("sanba", ("sanba",))),
                     priority={"paran": 3, "stomp": 2}, single_priority={"paran": 3, "stomp": 2, "sanba": 1},
                     group_pan={"sanba": 168})),
        Part("bass", BassLine("bass", kind="rootfifth", vol=46), pan=128),
        Part("lead", OrnamentedLead("sanshin", ScaleRules(leap_probability=0.1, leap_semitones=(4, 5, 7)), LEAD_MOTIFS,
                                    vol=46, gate=0.8, grace=0.45), pan=172),
        Part("fue", Heterophony("fue", delay=1, drop=0.25, shift=12, vol_ratio=0.7, lo=12, hi=35, min_dur=2),
             follow="lead", pan=100),
        Part("comp", Comp("sanshin_bk", kind="pulse8", vol=34, chordal=False), pan=70, min_channels=6),
        Part("chorus", Pad("chorus", vol=24), pan=128, min_channels=6),
        Part("vocal", Sing("voice", vel_ratio=1.3), pan=128, depends=("lead",), min_channels=6, requires=frozenset({"voice"}),
             ducks=("lead", "fue", "comp"), duck_ratio=0.35,
             duck_ratios=(("lead", 0.2),)),
    )
    mod_channels = {4: 1, 6: 2}

    def plan(self, rng: random.Random) -> SongPlan:
        family = rng.choice(list(FAMILIES))
        base = default_plan(self, rng)
        label, meter, swing, bpms, order = FAMILIES[family]
        base.bpm = rng.choice(bpms)
        base.summary = [f"Rhythm      : {label}", *base.summary]
        base.extra = dict(base.extra, family=family)
        base.order = list(order)
        for name in [n for n in base.sections if n not in order]:
            del base.sections[name]
        for sp in base.sections.values():
            retime(sp, meter, swing)
            sp.section = dataclasses.replace(sp.section, motifs=f"{family}:{sp.section.motifs}")
            sp.extra = dict(sp.extra, family=family)
        return base
