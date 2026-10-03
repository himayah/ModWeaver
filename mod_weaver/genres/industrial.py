"""industrial（旧 genres/industrial.py の宣言を機械変換したもの。DESIGN.md §6）。"""
from __future__ import annotations

from ..core.composer import RhythmMotif, ScaleRules
from ..core.model import ChordSpec, GmVoice
from ..core.synth_presets import PRESETS
from ..framework.gens import BassLine, Fx, Groove, Lead, hits
from ..framework.genre import Genre, Harmony, Instrument, Kit, Part, Section
from ..framework.context import Generator, MeasureCtx
from ..core.pitch import fold_into_range
from ..framework.registry import register_genre

C = ChordSpec


def _inst(key: str, gm: GmVoice, **changes) -> Instrument:
    patch = PRESETS[key]
    if changes:
        import dataclasses
        patch = dataclasses.replace(patch, **changes)
    return Instrument(patch=patch, gm=gm)

GROOVES = {
    "main": hits("kick", (0, 4, 8, 12), 60) + hits("snare", (4, 12), 52) + hits("clang", (2, 10), 40) + hits("clang", (6, 14), 32, 0.6) + hits("hat", (1, 3, 5, 7, 9, 11, 13, 15), 22, 0.7),
    "half": hits("kick", (0, 10), 58) + hits("snare", (8,), 54) + hits("clang", (3, 6, 14), 36),
    "metal": hits("clang", (0, 3, 6, 10, 12), 42) + hits("hat", (0, 2, 4, 6, 8, 10, 12, 14), 20),
    "fill": hits("snare", (8, 10, 12, 14), 50) + hits("clang", (13, 15), 44),
}
LEAD_MOTIFS = {
    "verse": (RhythmMotif(rows=(0, 4, 8)), RhythmMotif(rows=(0, 3, 6, 12)), RhythmMotif(rows=(0, 8, 10))),
}
PROGRESSIONS = (
    ("i-bII", (C(0, "min", label="i"), C(0, "min", label="i"), C(1, "maj", label="bII"), C(0, "min", label="i"))),
    ("i-bVI-bVII-i", (C(0, "min", label="i"), C(8, "maj", label="bVI"), C(10, "maj", label="bVII"), C(0, "min", label="i"))),
    ("i-iv-bII-i", (C(0, "min", label="i"), C(5, "min", label="iv"), C(1, "maj", label="bII"), C(0, "min", label="i"))),
)


# 金属パイプのリフ（16分の位置と、和音の構成音の並びの番号）。区間ごとに1つ選んで繰り返す
RIFFS = (((0, 0), (3, 0), (6, 1), (10, 0), (12, 2)), ((0, 0), (2, 1), (6, 0), (8, 2), (11, 1)),
         ((0, 0), (4, 0), (7, 2), (10, 1), (14, 0)))
PIPE_REGISTER = (12, 23)


class PipeRiff(Generator):
    """金属パイプのリフ: 区間ごとに選んだ1小節の型を、和音の構成音で繰り返す（旧 begin_pattern＋extra_measure）。"""

    def __init__(self, inst: str) -> None:
        self.inst = inst

    def section(self, ctx) -> None:
        riff = ctx.rng.choice(RIFFS)
        for m in ctx.measures():
            chord = m.m.chord
            pcs = sorted({t % 12 for t in chord.chord_tones}, key=lambda pc: (pc - chord.bass) % 12)
            for step, idx in riff:
                if step < m.m.steps:
                    m.note(step, self.inst, fold_into_range(pcs[idx % len(pcs)], *PIPE_REGISTER),
                           vel=m.scale_vol(40 if step == 0 else 34))


@register_genre
class IndustrialGenre(Genre):
    id = "industrial"
    display_name = "Industrial"
    description = "インダストリアル。歪んだビートと金属の打撃、うなる歪んだベースと工場の騒音"
    description_en = "Industrial: distorted beats and metal clangs, a roaring distorted bass and factory noise"
    title = "Iron Works"
    tempo_choices = (110, 114, 118, 122, 126, 130)

    instruments = {
        "kick": _inst("ind_kick", GmVoice(drum_note=36)),
        "snare": _inst("ind_snare", GmVoice(drum_note=40)),
        "clang": _inst("ind_metal_clang", GmVoice(drum_note=53)),
        "hat": _inst("drum_909_hat", GmVoice(drum_note=42)),
        "bass": _inst("bass_dist", GmVoice(program=38)),
        "pipe": _inst("ind_metal_pipe", GmVoice(program=14)),
        "lead": _inst("ind_buzz_lead", GmVoice(program=81)),
        "noise": _inst("fx_factory", GmVoice(program=122)),
    }
    harmony = Harmony(keys=(4, 2, 0, 9), mode="phrygian", progressions=PROGRESSIONS, n_progressions=2)
    sections = {
        "intro": Section(intensity=0.6, parts=frozenset({"fx", "pipe", "drums"}), groove="metal"),
        "a": Section(intensity=0.85, parts=frozenset({"fx", "pipe", "bass", "drums"}), fill=True),
        "b": Section(prog=1, intensity=1.0, parts=frozenset({"bass", "drums", "pipe", "lead", "fx"}), fill=True),
        "break": Section(intensity=0.7, parts=frozenset({"fx", "pipe", "drums"}), groove="half"),
        "outro": Section(intensity=0.6, parts=frozenset({"fx", "drums"}), groove="metal"),
    }
    form = ("intro", "a", "a", "b", "break", "a", "b", "b", "outro")
    parts = (
        Part("drums", Groove(GROOVES), pan=128,
             kit=Kit(groups=(("kick/snare", ("kick", "snare")), ("metal", ("clang", "hat"))),
                     priority={"snare": 2, "clang": 2},
                     group_pan={"metal": 170})),
        Part("bass", BassLine("bass", kind="pulse16", vol=44), pan=128),
        Part("pipe", PipeRiff("pipe"), pan=84),
        Part("lead", Lead("lead", ScaleRules(leap_probability=0.2, leap_semitones=(1, 3, 5, 7)), LEAD_MOTIFS,
                   vol=40, gate=0.7), pan=150),
        Part("fx", Fx("noise", every=2, vol=22), pan=100),
    )
    mod_channels = {6: 1}
