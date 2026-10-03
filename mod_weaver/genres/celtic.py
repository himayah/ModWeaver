"""celtic（ケルト音楽風のダンスチューン。NEW_GENRES_DESIGN.md §9）。

系統は seed で選ぶ: ``jig``（6/8）・``reel``（4/4・8分の連続）・``hornpipe``（付点にハネた 4/4）。
8小節の旋律を AABB（同じ区間名の繰り返し）で並べた曲を2つつなぐ「セット」。旋律は手続き的に作る（伝承曲は使わない）。
"""
from __future__ import annotations

import dataclasses
import random

from ..core.composer import RhythmMotif, ScaleRules
from ..core.model import ChordSpec, GmVoice
from ..core.pitch import CHORD_QUALITIES
from ..framework.context import Generator, MeasureCtx
from ..framework.gens import Arp, BassLine, Groove, hits
from ..framework.genre import Genre, Harmony, Kit, Part, Section
from ..framework.plan import Meter, SongPlan, Swing, default_plan
from ..framework.registry import register_genre
from ._ornament import Drone, Heterophony, OrnamentedLead, inst as _inst, retime

C = ChordSpec

JIG = Meter(12, 6, (6, 8))                   # 1拍＝付点4分（6 step）。BPM は付点4分の数
REEL = Meter(16, 4)
HORNPIPE = Meter(8, 2)                       # 8分の格子。Swing(18, 6) で付点にハネる
FAMILIES = {                                 # 名前: (表示, 拍子, スウィング, テンポの候補)
    "jig": ("Jig 6/8", JIG, None, (110, 114, 118, 122, 125)),
    "reel": ("Reel 4/4", REEL, None, (104, 108, 112, 116, 120)),
    "hornpipe": ("Hornpipe 4/4", HORNPIPE, Swing(18, 6), (88, 92, 96, 100, 104)),
}

GROOVES = {
    "jig:main": hits("bodhran", (0, 6), 56) + hits("bodhran", (4, 10), 34, 0.8) + hits("foot", (0,), 36),
    "reel:main": hits("bodhran", (0, 4, 8, 12), 52) + hits("bodhran", (2, 6, 10, 14), 28, 0.7)
                 + hits("foot", (0, 8), 34),
    "hornpipe:main": hits("bodhran", (0, 4), 54) + hits("bodhran", (2, 6), 32, 0.8) + hits("foot", (0,), 34),
}
LEAD_MOTIFS = {
    "jig": (RhythmMotif(rows=(0, 2, 4, 6, 8, 10)), RhythmMotif(rows=(0, 4, 6, 8, 10)),
            RhythmMotif(rows=(0, 2, 4, 6, 10)), RhythmMotif(rows=(0, 6, 8, 10))),
    "reel": (RhythmMotif(rows=(0, 2, 4, 6, 8, 10, 12, 14)), RhythmMotif(rows=(0, 2, 4, 6, 8, 10, 12)),
             RhythmMotif(rows=(0, 2, 4, 8, 10, 12, 14))),
    "hornpipe": (RhythmMotif(rows=(0, 1, 2, 3, 4, 5, 6, 7)), RhythmMotif(rows=(0, 1, 2, 3, 4, 6)),
                 RhythmMotif(rows=(0, 2, 3, 4, 5, 6, 7))),
}
STRUM = {                                    # 系統ごとのギターの刻み: (step, 音量)
    "jig": ((0, 40), (3, 28), (6, 36), (9, 28)),
    "reel": ((0, 40), (4, 34), (8, 38), (12, 34)),
    "hornpipe": ((0, 40), (2, 30), (4, 36), (6, 30)),
}
PROGRESSIONS = (
    ("I-bVII-I-bVII", (C(0, "maj", label="I"), C(10, "maj", label="bVII"), C(0, "maj", label="I"), C(10, "maj", label="bVII"))),
    ("I-IV-I-V", (C(0, "maj", label="I"), C(5, "maj", label="IV"), C(0, "maj", label="I"), C(7, "maj", label="V"))),
    ("I-bVII-IV-I", (C(0, "maj", label="I"), C(10, "maj", label="bVII"), C(5, "maj", label="IV"), C(0, "maj", label="I"))),
    ("i-bVII-bVI-bVII", (C(0, "min", label="i"), C(10, "maj", label="bVII"), C(8, "maj", label="bVI"), C(10, "maj", label="bVII"))),
)


class CelticStrum(Generator):
    """ギター（DADGAD 風の開放的なストローク）。系統ごとの刻み。"""

    def measure(self, m: MeasureCtx) -> None:
        for step, vol in STRUM[m.song.extra["family"]]:
            if step < m.m.steps:
                m.note(step, "gtr", m.m.chord.harmony, vel=m.scale_vol(vol), chord=CHORD_QUALITIES[m.m.quality],
                       strum_ms=12.0)


def _sec(parts, *, prog=0, intensity=0.8, measures=8, kind="") -> Section:
    return Section(prog=prog, measures=measures, intensity=intensity, parts=frozenset(parts), kind=kind)


@register_genre
class CelticGenre(Genre):
    id = "celtic"
    category = "genre"
    display_name = "Celtic Dance Tunes"
    description = "ケルト音楽風のダンスチューン。ジグ・リール・ホーンパイプ、AABB の反復、ドローンと前打音（伝承曲の旋律は使わない）"
    description_en = "Celtic-style dance tunes: jig, reel or hornpipe, AABB repeats, drone and cuts (no traditional melodies)"
    title = "Celtic Set"
    tempo_choices = tuple(sorted({b for f in FAMILIES.values() for b in f[3]}))

    instruments = {
        "bodhran": _inst("celt_bodhran", GmVoice(drum_note=41)),
        "foot": _inst("perc_stomp", GmVoice(drum_note=35)),
        "bass": _inst("bass_finger", GmVoice(program=33)),
        "gtr": _inst("gtr_acoustic", GmVoice(program=25)),
        "fiddle": _inst("orch_violin", GmVoice(program=110), name="Fiddle", volume=44),
        "whistle": _inst("wind_flute", GmVoice(program=78), name="Whistle", volume=30),
        "drone": _inst("celt_drone", GmVoice(program=109)),
        "harp": _inst("keys_harp", GmVoice(program=46)),
    }
    harmony = Harmony(keys=(2, 7, 9, 4), mode="mixolydian", progressions=PROGRESSIONS, n_progressions=2)
    _tune = {"drone", "bass", "drums", "comp", "lead"}
    sections = {
        "intro": _sec({"drone", "comp", "bass"}, intensity=0.5, measures=4),
        "a": _sec(_tune), "b": _sec(_tune, prog=1, intensity=0.9),
        "c": _sec(_tune | {"harp"}, prog=1, intensity=0.85), "d": _sec(_tune | {"harp"}, intensity=1.0),
        "outro": _sec({"drone", "comp", "lead"}, intensity=0.5, measures=4),
    }
    form = ("intro", "a", "a", "b", "b", "c", "c", "d", "d", "outro")
    parts = (
        Part("drums", Groove(GROOVES, groove_name=lambda sp: f"{sp.extra['family']}:{sp.section.groove}"), pan=128,
             kit=Kit(groups=(("bodhran", ("bodhran",)), ("foot", ("foot",))),
                     priority={"bodhran": 2, "foot": 1}, single_priority={"bodhran": 2, "foot": 1})),
        Part("bass", BassLine("bass", kind="rootfifth", vol=48), pan=128),
        Part("comp", CelticStrum(), pan=84),
        Part("lead", OrnamentedLead("fiddle", ScaleRules(leap_probability=0.15, leap_semitones=(3, 4, 5)), LEAD_MOTIFS,
                                    vol=46, gate=0.85, grace=0.4, roll=0.2), pan=172),
        Part("whistle", Heterophony("whistle", delay=1, drop=0.2, shift=12, vol_ratio=0.7, lo=12, hi=35, min_dur=1),
             follow="lead", pan=100, min_channels=6),
        Part("drone", Drone("drone", 30), pan=128, min_channels=6),
        Part("harp", Arp("harp", (12, 28), vol=34), pan=70, min_channels=8),
    )
    mod_channels = {4: 1, 6: 2, 8: 1}

    def plan(self, rng: random.Random) -> SongPlan:
        family = rng.choice(list(FAMILIES))
        base = default_plan(self, rng)
        label, meter, swing, bpms = FAMILIES[family]
        base.bpm = rng.choice(bpms)
        base.summary = [f"Rhythm      : {label}", *base.summary]
        base.extra = dict(base.extra, family=family)
        for sp in base.sections.values():
            retime(sp, meter, swing)
            sp.section = dataclasses.replace(sp.section, motifs=family)
            sp.extra = dict(sp.extra, family=family)
        return base
