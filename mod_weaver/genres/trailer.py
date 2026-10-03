"""trailer（旧 genres/trailer.py の宣言を機械変換したもの。DESIGN.md §6）。"""
from __future__ import annotations

import dataclasses

from ..core.composer import RhythmMotif, ScaleRules
from ..core.model import ChordSpec, GmVoice
from ..core.synth_presets import PRESETS
from ..framework.gens import BassLine, Groove, Lead, Pad, hits
from ..framework.genre import Genre, Harmony, Instrument, Kit, Part, Section
from ..framework.context import Generator, MeasureCtx
from ..core.pitch import fold_into_range
from ..framework.gens import Buildup
from ..framework.score import NoteEvent
from ..framework.registry import register_genre

C = ChordSpec


def _inst(key: str, gm: GmVoice, **changes) -> Instrument:
    patch = PRESETS[key]
    if changes:
        import dataclasses
        patch = dataclasses.replace(patch, **changes)
    return Instrument(patch=patch, gm=gm)

GROOVES = {
    "main": hits("taiko", (0, 6, 8), 58) + hits("taiko", (14,), 44, 0.6),
    "full": hits("taiko", (0, 4, 6, 8, 12, 14), 60),
    "pulse": hits("taiko", (0, 4, 8, 12), 54),
}
LEAD_MOTIFS = {
    "verse": (RhythmMotif(rows=(0, 8)), RhythmMotif(rows=(0, 12)), RhythmMotif(rows=(0, 4, 8))),
}
PROGRESSIONS = (
    ("i-VI-III-VII", (C(0, "min", label="i"), C(8, "maj", label="VI"), C(3, "maj", label="III"), C(10, "maj", label="VII"))),
    ("i-bVI-bVII-i", (C(0, "min", label="i"), C(8, "maj", label="bVI"), C(10, "maj", label="bVII"), C(0, "min", label="i"))),
)


SPIC_ACCENTS = (0, 3, 6, 8, 11, 14)           # 3+3+2 のアクセント
TOM_STEPS = (10, 12, 13, 14, 15)                # 第3幕の小節末のタム


class TrailerDrums(Groove):
    """太鼓・タム・スネア。区間の tags が役割を決める: "groove" は型、"hits" は偶数小節の衝撃（太鼓）、
    "build" はスネアのビルドアップ、"toms" は奇数小節の末のタム。"""

    def __init__(self, grooves, **kw) -> None:
        super().__init__(grooves, **kw)
        self.buildup = Buildup("snare")

    def measure(self, m: MeasureCtx) -> None:
        tags = m.plan.section.tags
        if "groove" in tags:
            super().measure(m)
        if "hits" in tags and m.m.index % 2 == 0:
            m.note(0, "taiko", vel=64)
        if "build" in tags:
            self.buildup.measure(m)
        if "toms" in tags and m.m.index % 2 == 1:
            bass = m.m.chord.bass
            for i, step in enumerate(TOM_STEPS):
                m.note(step, "tom", fold_into_range(bass + 12 - i * 2, 12, 23), vel=48 + i * 3)


class Braam(Generator):
    """衝撃（"hits"）と、2小節ごとのブラーム（"braam"）。"""

    def __init__(self, inst: str) -> None:
        self.inst = inst

    def measure(self, m: MeasureCtx) -> None:
        tags = m.plan.section.tags
        if m.m.index % 2:
            return
        if "hits" in tags:
            m.note(0, self.inst, m.m.chord.bass, vel=m.scale_vol(60))
        elif "braam" in tags:
            m.note(0, self.inst, m.m.chord.bass, vel=m.scale_vol(56))


class Spiccato(Generator):
    """刻むスピッカート（根音、6・14 step 目だけ5度）。"""

    def __init__(self, inst: str) -> None:
        self.inst = inst

    def measure(self, m: MeasureCtx) -> None:
        root = fold_into_range(m.m.chord.bass, 12, 23)
        fifth = fold_into_range(m.m.chord.bass + 7, 12, 23)
        for step in range(min(16, m.m.steps)):
            m.note(step, self.inst, fifth if step in (6, 14) else root,
                   vel=m.scale_vol(44 if step in SPIC_ACCENTS else 30))


class TrailerFx(Generator):
    """衝撃音（"hits" の区間の頭、act3 の頭）と、ビルドアップの上昇音。"""

    def __init__(self, impact: str, riser: str) -> None:
        self.impact = impact
        self.riser = riser

    def measure(self, m: MeasureCtx) -> None:
        tags = m.plan.section.tags
        if "hits" in tags and m.m.index == 0:
            m.note(0, self.impact, vel=60)
        if m.plan.kind == "act3" and m.m.index == 0:
            m.note(0, self.impact, vel=60)
        if "build" in tags and m.m.index % 4 == 2:
            m.note(0, self.riser, vel=48)


def hold_final(sec, score) -> None:
    """final: 一撃の後は余韻だけ（旧 compose_measure の上書き）。2小節目以降の音を消し、持続音（低弦・合唱）は
    2小節で止める。"""
    if sec.kind != "final":
        return
    first = sec.measures[0]
    score.mute(tuple(score.parts), sec.measures[1].start, sec.steps)
    for part in ("bass", "pad"):
        score.parts[part] = [dataclasses.replace(e, dur=2 * first.steps)
                             if isinstance(e, NoteEvent) and e.step < first.steps and e.dur is None else e
                             for e in score.parts.get(part, [])]


@register_genre
class TrailerGenre(Genre):
    id = "trailer"
    category = "style"
    display_name = "Cinematic Trailer"
    description = "映画予告編風。大太鼓と金管の衝撃、刻む弦、合唱で盛り上がる3幕構成"
    description_en = "Cinematic trailer style: taiko and brass hits, driving strings and choir in three acts"
    title = "Trailer: Three Acts"
    tempo_choices = (90, 92, 94, 96, 98, 100)

    instruments = {
        "taiko": _inst("perc_taiko", GmVoice(program=116)),
        "tom": _inst("drum_tom", GmVoice(drum_note=45)),
        "snare": _inst("march_snare", GmVoice(drum_note=38)),
        "braam": _inst("brass_braam", GmVoice(program=61)),
        "spic": _inst("str_spiccato", GmVoice(program=48)),
        "cello": _inst("orch_cello", GmVoice(program=42)),
        "vln": _inst("orch_violin", GmVoice(program=48)),
        "riser": _inst("fx_riser", GmVoice(program=97)),
        "impact": _inst("fx_impact", GmVoice(program=55)),
        "choir": _inst("vox_choir", GmVoice(program=52), volume=36),
    }
    harmony = Harmony(keys=(2, 0), mode="aeolian", progressions=PROGRESSIONS, n_progressions=2)
    sections = {
        "act1": Section(intensity=0.55, parts=frozenset({"drums", "braam", "fx"}), tags=frozenset({"hits"})),
        "act2": Section(intensity=0.75, parts=frozenset({"drums", "braam", "spic", "bass"}),
                        tags=frozenset({"braam", "groove"})),
        "riser": Section(prog=1, intensity=0.85, parts=frozenset({"drums", "spic", "bass", "fx"}), groove="pulse",
                         tags=frozenset({"build", "groove"})),
        "act3": Section(prog=1, intensity=1.0, parts=frozenset({"drums", "braam", "bass", "pad", "spic", "lead", "fx"}),
                        groove="full", key_offset=1, tags=frozenset({"braam", "toms", "groove"})),
        "final": Section(prog=1, intensity=0.9, parts=frozenset({"drums", "braam", "fx", "bass", "pad"}), key_offset=1,
                         tags=frozenset({"hits"})),
    }
    form = ("act1", "act1", "act2", "act2", "riser", "act3", "act3", "final")
    parts = (
        Part("drums", TrailerDrums(GROOVES), pan=128,
             kit=Kit(groups=(("taiko", ("taiko",)), ("toms/snare", ("snare", "tom"))),
                     priority={"snare": 2},
                     single_priority={"taiko": 3, "snare": 2},
                     group_pan={"toms/snare": 150})),
        Part("braam", Braam("braam"), pan=110),
        Part("spic", Spiccato("spic"), pan=80),
        Part("bass", BassLine("cello", kind="half", vol=48), pan=128),
        Part("pad", Pad("choir", vol=38), pan=170),
        Part("lead", Lead("vln", ScaleRules(leap_probability=0.35, leap_semitones=(3, 4, 5, 7, 12)), LEAD_MOTIFS,
                   vol=50, gate=1.0, vibrato=0x24), pan=90),
        Part("fx", TrailerFx("impact", "riser"), pan=128, min_channels=8),
    )
    mod_channels = {6: 1, 8: 2}

    def finalize_section(self, sec, score, rng) -> None:
        hold_final(sec, score)
