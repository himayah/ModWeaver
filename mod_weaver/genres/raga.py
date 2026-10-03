"""raga（ヒンドゥスターニー古典音楽風）。

タンプーラのドローン（Pa・Sa・Sa・低い Sa）の上で、シタール風の旋律がアーラープ（拍なし・長い音）→ジョール（拍が現れる）→
ガット（タブラの16拍ティーンタール）→ジャラー（最速）へ進む。ラーガは seed で選ぶ（yaman・bhairav・bhairavi・kafi・todi）。
平均律の近似（微分音は使わない）。実在の曲・奏者・流派は使わない。
"""
from __future__ import annotations

import dataclasses
import random

from ..core.composer import RhythmMotif, ScaleRules
from ..core.model import ChordSpec, GmVoice
from ..core.pitch import MODES, Scale, fold_into_range
from ..framework.context import Generator, MeasureCtx
from ..framework.genre import Genre, Harmony, Kit, Part, Section
from ..framework.plan import Meter, SongPlan, default_plan
from ..framework.registry import register_genre
from ._ornament import Heterophony, OrnamentedLead, WithTempo, inst as _inst

C = ChordSpec

METER = Meter(64, 4, (16, 4))                  # 1 小節＝ティーンタールの1周期（16拍＝64 step。1拍＝4 step）
RAGAS = {                                      # 名前: (音階, 説明)
    "yaman": ("lydian", "Yaman (evening, raised 4th)"),
    "bhairav": ("phrygian_dominant", "Bhairav (morning, flat 2nd and 6th)"),
    "bhairavi": ("phrygian", "Bhairavi"),
    "kafi": ("dorian", "Kafi"),
    "todi": ("todi", "Todi"),
}
TEMPO = {"alap": (0.45, 0.45), "jor": (0.6, 0.8), "gat1": (1.0, 1.0), "gat2": (1.0, 1.15), "jhala": (1.3, 1.6),
         "outro": (1.2, 0.6)}
THEKA = ("dha", "dhin", "dhin", "dha", "dha", "dhin", "dhin", "dha", "dha", "tin", "tin", "ta", "ta", "dhin", "dhin", "dha")
BOLS = {"dha": ("na", "ge"), "dhin": ("tin", "ge"), "tin": ("tin",), "ta": ("na",)}
LEAD_MOTIFS = {
    "alap": (RhythmMotif(rows=(0,)), RhythmMotif(rows=(0, 32)), RhythmMotif(rows=(0, 24, 40))),
    "jor": (RhythmMotif(rows=(0, 8, 16, 24, 32, 40, 48, 56)), RhythmMotif(rows=(0, 12, 16, 28, 32, 44, 48, 60)),
            RhythmMotif(rows=(0, 8, 12, 16, 24, 28, 32, 40))),
    "gat": (RhythmMotif(rows=tuple(range(0, 64, 4))), RhythmMotif(rows=tuple(range(0, 64, 2))),
            RhythmMotif(rows=(0, 4, 6, 8, 12, 16, 20, 22, 24, 28, 32, 36, 38, 40, 44, 48, 52, 54, 56, 60))),
}
PROGRESSIONS = (("Sa", (C(0, "maj", label="Sa"),)),)


class Tanpura(Generator):
    """タンプーラ: 4弦を4拍ごとに Pa・Sa・Sa・低い Sa の順で弾く（1周期＝16拍）。"""

    def measure(self, m: MeasureCtx) -> None:
        tonic = m.plan.tonic
        sa = fold_into_range(tonic, 12, 23)
        pa = fold_into_range(tonic + 7, 6, 17)
        low = sa - 12 if sa - 12 >= 0 else sa
        for step, note in ((0, pa), (16, sa), (32, sa), (48, low)):
            m.note(step, "tanpura", note, vel=m.scale_vol(30), dur=None)


class Teental(Generator):
    """タブラのティーンタール（16拍のテカー）。ガット2・ジャラーは16分の装飾を足す。"""

    def measure(self, m: MeasureCtx) -> None:
        kind = m.plan.kind
        for i, bol in enumerate(THEKA):
            step = 4 * i
            for inst in BOLS[bol]:
                m.note(step, inst, vel=m.scale_drum(46 if bol == "dha" else 38))
            if kind in ("gat2", "jhala") and m.rng.random() < 0.5:
                m.note(step + 2, "na", vel=m.scale_drum(24))
            if kind == "jhala":
                for sub in (1, 3):
                    m.note(step + sub, "tin", vel=m.scale_drum(18))


def _sec(parts, *, intensity, measures, motifs, kind="") -> Section:
    return Section(measures=measures, intensity=intensity, parts=frozenset(parts), motifs=motifs, meter=METER, kind=kind)


@register_genre
class RagaGenre(Genre):
    id = "raga"
    category = "genre"
    display_name = "Raga (Hindustani Style)"
    description = "ヒンドゥスターニー古典風。タンプーラのドローン、シタール風の旋律、アーラープからガットへ加速するタブラ（ラーガは seed で選ぶ）"
    description_en = "Hindustani raga style: tanpura drone, sitar-like melody, alap to gat with accelerating tabla (the raga is chosen by the seed)"
    title = "Raga Evening"
    tempo_choices = (88, 96, 104, 112)

    instruments = {
        "tanpura": _inst("raga_tanpura", GmVoice(program=104), volume=36),
        "sitar": _inst("raga_sitar", GmVoice(program=104)),
        "bansuri": _inst("wind_flute", GmVoice(program=72), name="Bansuri", volume=32),
        "ge": _inst("raga_tabla_ge", GmVoice(drum_note=41)),
        "na": _inst("raga_tabla_na", GmVoice(drum_note=60)),
        "tin": _inst("raga_tabla_tin", GmVoice(drum_note=61)),
    }
    harmony = Harmony(keys=(2, 4, 7, 9, 0), mode="ionian", progressions=PROGRESSIONS, n_progressions=1)
    _melody = {"sitar", "tanpura"}
    sections = {
        "alap": _sec(_melody, intensity=0.45, measures=2, motifs="alap"),
        "jor": _sec(_melody, intensity=0.65, measures=2, motifs="jor"),
        "gat1": _sec(_melody | {"tabla"}, intensity=0.8, measures=3, motifs="gat"),
        "gat2": _sec(_melody | {"tabla"}, intensity=0.9, measures=3, motifs="gat"),
        "jhala": _sec(_melody | {"tabla"}, intensity=1.0, measures=2, motifs="gat"),
        "outro": _sec(_melody, intensity=0.5, measures=1, motifs="alap"),
    }
    form = ("alap", "jor", "gat1", "gat2", "jhala", "outro")
    parts = (
        Part("tanpura", WithTempo(Tanpura(), lambda sp: TEMPO[sp.name]), pan=128),
        Part("sitar", OrnamentedLead("sitar", ScaleRules(leap_probability=0.08, leap_semitones=(2, 3, 4)), LEAD_MOTIFS,
                                     vol=46, gate=0.92, scoop=0.45, grace=0.35, roll=0.25), pan=150),
        Part("tabla", Teental(), pan=100, min_channels=0,
             kit=Kit(groups=(("ge", ("ge",)), ("na/tin", ("na", "tin"))), priority={"na": 2, "tin": 1},
                     single_priority={"ge": 2, "na": 2, "tin": 1}, group_pan={"na/tin": 150})),
        Part("bansuri", Heterophony("bansuri", delay=2, drop=0.3, shift=0, vol_ratio=0.7, lo=12, hi=35, min_dur=2),
             follow="sitar", pan=90, min_channels=6),
    )
    mod_channels = {4: 1, 6: 2}

    def plan(self, rng: random.Random) -> SongPlan:
        base = default_plan(self, rng)
        name = rng.choice(list(RAGAS))
        mode, label = RAGAS[name]
        reg = self.harmony.registers.melody
        base.summary = [f"Raga        : {label}", *base.summary]
        base.extra = dict(base.extra, raga=name)
        for sp in base.sections.values():
            scale = Scale(sp.tonic, MODES[mode])
            notes = tuple(scale.notes_in(*reg))               # 旋律はラーガの音だけ（強拍もどの音でもよい）
            fix = lambda ch: dataclasses.replace(ch, chord_tones=notes, scale_tones=notes)       # noqa: E731
            sp.scale = scale
            sp.measures = tuple(dataclasses.replace(mp, chord=fix(mp.chord), next_chord=fix(mp.next_chord))
                                for mp in sp.measures)
            sp.extra = dict(sp.extra, raga=name)
        return base
