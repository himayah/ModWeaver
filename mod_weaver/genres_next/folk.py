"""folk（旧 genres/folk.py の宣言を機械変換したもの。FRAMEWORK_REDESIGN.md §15）。"""
from __future__ import annotations

from ..core.composer import RhythmMotif, ScaleRules
from ..core.model import ChordSpec, GmVoice
from ..core.synth_presets import PRESETS
from ..framework.gens import BassLine, Comp, Groove, Layer, Lead, hits
from ..framework.genre import Genre, Harmony, Instrument, Kit, Part, Section
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
    "main": hits("stomp", (0, 8), 56) + hits("clap", (4, 12), 44) + hits("tamb", (2, 6, 10, 14), 20, 0.7),
}
LEAD_MOTIFS = {
    "verse": (RhythmMotif(rows=(0, 2, 4, 6, 8, 12)), RhythmMotif(rows=(0, 4, 6, 8, 10, 12)), RhythmMotif(rows=(0, 2, 4, 8, 12))),
    "reel": (RhythmMotif(rows=(0, 2, 4, 6, 8, 10, 12, 14)), RhythmMotif(rows=(0, 2, 4, 6, 8, 10, 12)), RhythmMotif(rows=(0, 2, 3, 4, 6, 8, 10, 12, 14))),
}
PROGRESSIONS = (
    ("I-IV-I-V", (C(0, "maj", label="I"), C(5, "maj", label="IV"), C(0, "maj", label="I"), C(7, "maj", label="V"))),
    ("I-V-vi-IV", (C(0, "maj", label="I"), C(7, "maj", label="V"), C(9, "min", label="vi"), C(5, "maj", label="IV"))),
    ("I-bVII-IV-I", (C(0, "maj", label="I"), C(10, "maj", label="bVII"), C(5, "maj", label="IV"), C(0, "maj", label="I"))),
)


GRACE_PROB = 0.3                               # 前打音を付ける確率（直前が空いている音だけ）


class FiddleLead(Lead):
    """フィドルの前打音: 直前の step が空いている音に、確率で1つ上の音階音を16分で先行させる（旧 lead の上書き）。"""

    def section(self, ctx) -> None:
        super().section(ctx)
        events = ctx.own_events()
        occupied = {e.step for e in events if isinstance(e, NoteEvent)}
        added = []
        for m in ctx.plan.measures:
            for e in sorted((e for e in events if isinstance(e, NoteEvent) and m.start < e.step < m.start + m.steps),
                            key=lambda e: e.step):
                if e.step - 1 in occupied or ctx.rng.random() >= GRACE_PROB:
                    continue
                above = [t for t in m.chord.scale_tones if t > e.pitch]
                if above:
                    added.append(NoteEvent(e.step - 1, e.inst, above[0], max(1, (e.vel or 40) - 10)))
        events.extend(added)
        events.sort(key=lambda e: e.step)


@register_genre
class FolkGenre(Genre):
    id = "folk"
    display_name = "Folk"
    description = "フォーク。アコースティックギターのストロークとフィドル、素朴な進行"
    description_en = "Folk: strummed acoustic guitar and fiddle over simple progressions"
    title = "Folk Road"
    tempo_choices = (96, 100, 104, 108, 112, 116)

    instruments = {
        "stomp": _inst("perc_stomp", GmVoice(drum_note=35)),
        "clap": _inst("fb_clap", GmVoice(drum_note=39)),
        "tamb": _inst("perc_tambourine", GmVoice(drum_note=54)),
        "bass": _inst("swing_walk_bass", GmVoice(program=32)),
        "fiddle": _inst("orch_violin", GmVoice(program=110), name="Fiddle", volume=42),
        "whistle": _inst("wind_flute", GmVoice(program=78), name="Whistle", volume=30),
        "gtr": _inst("gtr_acoustic", GmVoice(program=25)),
    }
    harmony = Harmony(keys=(7, 2, 0, 9), mode="ionian", progressions=PROGRESSIONS, n_progressions=2)
    sections = {
        "intro": Section(intensity=0.6, parts=frozenset({"drums", "comp"})),
        "verse": Section(intensity=0.7, parts=frozenset({"lead", "bass", "drums", "comp"})),
        "chorus": Section(prog=1, intensity=0.9, parts=frozenset({"lead", "bass", "drums", "comp"})),
        "instrumental": Section(intensity=1.0, parts=frozenset({"lead", "bass", "drums", "comp"}), motifs="reel"),
        "outro": Section(intensity=0.6, parts=frozenset({"bass", "drums", "comp"})),
    }
    form = ("intro", "verse", "chorus", "verse", "instrumental", "chorus", "outro")
    parts = (
        Part("drums", Groove(GROOVES), pan=128,
             kit=Kit(groups=(("stomp/clap", ("stomp", "clap")), ("tambourine", ("tamb",))),
                     priority={"clap": 3, "stomp": 2},
                     single_priority={"stomp": 2, "clap": 3, "tamb": 1},
                     group_pan={"tambourine": 164})),
        Part("bass", BassLine("bass", kind="rootfifth", vol=54), pan=128),
        Part("comp", Comp("gtr", kind="pulse8", vol=38, strum_ms=14.0), pan=84),
        Part("lead", FiddleLead("fiddle", ScaleRules(leap_probability=0.12, leap_semitones=(3, 4, 5)), LEAD_MOTIFS,
                   vol=46, gate=0.9, vibrato=0x23), pan=172),
        Part("whistle", Layer("whistle", vol=24, register=(24, 35)), follow="lead", pan=100, min_channels=6),
    )
    mod_channels = {4: 2, 6: 1}
