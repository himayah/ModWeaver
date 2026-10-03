"""reggae（レゲエ／スカ風）。系統は seed で選ぶ: ``roots``（ワンドロップ。66〜82 BPM）と ``ska``（150〜172 BPM の4つ打ち寄り）。

3拍目だけを打つワンドロップ（キックとリムを3拍目に）、裏拍のスキャンク（ギターの短い和音）、重く間のあるベース、
オルガンのバブル。dub 区間ではスキャンクのエコーを足す。
"""
from __future__ import annotations

import random

from ..core.composer import RhythmMotif, ScaleRules
from ..core.model import ChordSpec, GmVoice
from ..core.pitch import CHORD_QUALITIES, fold_into_range
from ..framework.context import Generator, MeasureCtx
from ..framework.gens import Comp, Echo, Groove, Lead, hits
from ..framework.genre import Genre, Harmony, Kit, Part, Section
from ..framework.plan import SongPlan, default_plan
from ..framework.registry import register_genre
from ._ornament import inst as _inst

C = ChordSpec

FAMILIES = {"roots": ("Roots (one drop)", (66, 70, 74, 78, 82)), "ska": ("Ska", (150, 156, 162, 168, 172))}
GROOVES = {
    "roots:main": hits("kick", (8,), 56) + hits("rim", (8,), 48) + hits("hat", tuple(range(0, 16, 2)), 24)
                  + hits("hat", (3, 11), 14, 0.5),
    "ska:main": hits("kick", (0, 8), 54) + hits("snare", (4, 12), 46) + hits("hat", tuple(range(0, 16, 2)), 26),
}
BASS = {"roots": ((0, "r", 56), (6, "f", 44), (8, "r", 50), (12, "o", 44)),
        "ska": ((0, "r", 52), (4, "f", 44), (8, "r", 50), (12, "f", 44))}
LEAD_MOTIFS = {
    "verse": (RhythmMotif(rows=(0, 6, 10)), RhythmMotif(rows=(2, 8, 12)), RhythmMotif(rows=(0, 4, 8, 14))),
    "chorus": (RhythmMotif(rows=(0, 3, 6, 8, 12)), RhythmMotif(rows=(0, 4, 6, 10)), RhythmMotif(rows=(2, 6, 8, 12, 14))),
}
PROGRESSIONS = (
    ("i-iv-i-iv", (C(0, "min", label="i"), C(5, "min", label="iv"), C(0, "min", label="i"), C(5, "min", label="iv"))),
    ("i-bVII-bVI-bVII", (C(0, "min", label="i"), C(10, "maj", label="bVII"), C(8, "maj", label="bVI"), C(10, "maj", label="bVII"))),
    ("i-iv-bVII-i", (C(0, "min", label="i"), C(5, "min", label="iv"), C(10, "maj", label="bVII"), C(0, "min", label="i"))),
)


class Skank(Generator):
    """スキャンク: 裏拍（2・6・10・14）の短い和音。"""

    inst = "gtr"

    def measure(self, m: MeasureCtx) -> None:
        shape = CHORD_QUALITIES[m.m.quality]
        for step in (2, 6, 10, 14):
            m.note(step, "gtr", m.m.chord.harmony, vel=m.scale_vol(38 if step % 8 == 6 else 32), chord=shape, dur=1)


class SkaBass(Generator):
    def measure(self, m: MeasureCtx) -> None:
        reg = m.genre.harmony.registers.bass
        root = m.m.chord.bass
        for step, what, vol in BASS[m.song.extra["family"]]:
            note = {"r": root, "f": fold_into_range(root + 7, *reg), "o": fold_into_range(root + 12, reg[0], reg[1] + 12)}[what]
            m.note(step, "bass", note, vel=m.scale_vol(vol), dur=4 if what == "r" else 2)


def _sec(parts, *, prog=0, intensity=0.8, measures=8, motifs="verse") -> Section:
    return Section(prog=prog, measures=measures, intensity=intensity, parts=frozenset(parts), motifs=motifs)


@register_genre
class ReggaeGenre(Genre):
    id = "reggae"
    category = "genre"
    display_name = "Reggae"
    description = "レゲエ／スカ風。ワンドロップ、裏拍のスキャンク、重く間のあるベース、オルガンのバブルとダブのエコー"
    description_en = "Reggae / ska style: one-drop beat, offbeat skank, heavy spacious bass, organ bubble and dub echo"
    title = "Reggae Roots"
    tempo_choices = tuple(sorted({b for f in FAMILIES.values() for b in f[1]}))

    instruments = {
        "kick": _inst("drum_pop_kick", GmVoice(drum_note=36)),
        "rim": _inst("drum_rim", GmVoice(drum_note=37)),
        "snare": _inst("drum_pop_snare", GmVoice(drum_note=38)),
        "hat": _inst("drum_909_hat", GmVoice(drum_note=42)),
        "bass": _inst("bass_deep", GmVoice(program=33), volume=50),
        "gtr": _inst("gtr_clean_cut", GmVoice(program=28)),
        "organ": _inst("keys_organ", GmVoice(program=16), volume=30),
        "melodica": _inst("wind_flute", GmVoice(program=22), name="Melodica", volume=38),
    }
    harmony = Harmony(keys=(9, 2, 4, 7), mode="aeolian", progressions=PROGRESSIONS, n_progressions=2)
    _band = {"drums", "bass", "comp"}
    sections = {
        "intro": _sec(_band, intensity=0.55, measures=4),
        "verse": _sec(_band | {"organ", "lead"}, intensity=0.7),
        "chorus": _sec(_band | {"organ", "lead"}, prog=1, intensity=0.9, motifs="chorus"),
        "dub": _sec(_band | {"organ"}, intensity=0.6),
        "outro": _sec(_band, intensity=0.5, measures=4),
    }
    form = ("intro", "verse", "chorus", "verse", "dub", "chorus", "outro")
    parts = (
        Part("drums", Groove(GROOVES, groove_name=lambda sp: f"{sp.extra['family']}:{sp.section.groove}"), pan=128,
             kit=Kit(groups=(("kick/snare", ("kick", "snare", "rim")), ("hat", ("hat",))),
                     priority={"kick": 3, "snare": 2, "rim": 2}, single_priority={"kick": 3, "snare": 2, "rim": 2, "hat": 1},
                     group_pan={"hat": 164})),
        Part("bass", SkaBass(), pan=128),
        Part("comp", Skank(), pan=84),
        Part("lead", Lead("melodica", ScaleRules(leap_probability=0.1, leap_semitones=(3, 5)), LEAD_MOTIFS,
                          vol=40, gate=0.8, vibrato=0x23), pan=172),
        Part("organ", Comp("organ", kind="offbeat", vol=28, chordal=False), pan=100, min_channels=6),
        Part("dub echo", Echo(delay=6, ratio=0.45, repeats=2), follow="comp", pan=60, min_channels=8),
    )
    mod_channels = {4: 1, 6: 2, 8: 1}

    def plan(self, rng: random.Random) -> SongPlan:
        family = rng.choice(list(FAMILIES))
        base = default_plan(self, rng)
        label, bpms = FAMILIES[family]
        base.bpm = rng.choice(bpms)
        base.summary = [f"Rhythm      : {label}", *base.summary]
        base.extra = dict(base.extra, family=family)
        for sp in base.sections.values():
            sp.extra = dict(sp.extra, family=family)
        return base
