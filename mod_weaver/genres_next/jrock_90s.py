"""jrock-90s（旧 genres/jrock_90s.py の宣言を機械変換したもの。FRAMEWORK_REDESIGN.md §15）。"""
from __future__ import annotations

from ..core.composer import RhythmMotif, ScaleRules
from ..core.model import ChordSpec, GmVoice
from ..core.synth_presets import PRESETS
from ..framework.gens import Arp, BassLine, Echo, Groove, Layer, Lead, hits
from ..framework.genre import Genre, Harmony, Instrument, Kit, Part, Section
from ..framework.context import Generator, MeasureCtx
from ..framework.registry import register_genre

C = ChordSpec


def _inst(key: str, gm: GmVoice, **changes) -> Instrument:
    patch = PRESETS[key]
    if changes:
        import dataclasses
        patch = dataclasses.replace(patch, **changes)
    return Instrument(patch=patch, gm=gm)

GROOVES = {
    "main": hits("kick", (0, 3, 8, 10), 60) + hits("snare", (4, 12), 56) + hits("hat", (0, 2, 4, 6, 8, 10, 12, 14), 34),
    "drive": hits("kick", (0, 2, 8, 10), 60) + hits("snare", (4, 12), 58) + hits("hat", (0, 2, 4, 6, 8, 10, 12, 14), 36),
    "fill": hits("snare", (8, 10, 11, 12, 13, 14, 15), 54),
    "crash": hits("crash", (0,), 60),
}
LEAD_MOTIFS = {
    "verse": (RhythmMotif(rows=(0, 2, 4, 6, 8, 12)), RhythmMotif(rows=(0, 4, 6, 8, 10, 12))),
    "chorus": (RhythmMotif(rows=(0, 4, 8, 12)), RhythmMotif(rows=(0, 2, 4, 8, 12, 14))),
    "solo": (RhythmMotif(rows=(0, 1, 2, 3, 4, 6, 8, 10, 12, 13, 14)), RhythmMotif(rows=(0, 2, 3, 4, 8, 9, 10, 12))),
}
PROGRESSIONS = (
    ("bVI-iv-v-i", (C(8, "maj", label="bVI"), C(5, "min", label="iv"), C(7, "min", label="v"), C(0, "min", label="i"))),
    ("i-VI-VII-i", (C(0, "min", label="i"), C(8, "maj", label="VI"), C(10, "maj", label="VII"), C(0, "min", label="i"))),
    ("VI-VII-v-i", (C(8, "maj", label="VI"), C(10, "maj", label="VII"), C(7, "min", label="v"), C(0, "min", label="i"))),
)


class PowerChop(Generator):
    """パワーコード（単音のディストーションギター）を8分で刻む（強拍を強く。旧 comp の上書き）。"""

    def __init__(self, inst: str, strong: int, weak: int) -> None:
        self.inst = inst
        self.strong = strong
        self.weak = weak

    def measure(self, m: MeasureCtx) -> None:
        for i, step in enumerate(range(0, min(16, m.m.steps), 2)):
            m.note(step, self.inst, m.m.chord.harmony, vel=m.scale_drum(self.strong if i % 2 == 0 else self.weak))


class Guitars(Generator):
    """歪んだギター（パワーコードの刻み）とクリーンギター（アルペジオ）は、旧版では4chでは同じチャンネルに畳まれ、
    6ch以上では別のチャンネルだった。1つのパートにして Kit で別の lane にする。区間の tags に "clean" が
    あればアルペジオ、無ければパワーコード（同時には鳴らさない）。"""

    def __init__(self, chop: Generator, arp: Generator) -> None:
        self.chop = chop
        self.arp = arp

    def section(self, ctx) -> None:
        (self.arp if "clean" in ctx.plan.section.tags else self.chop).section(ctx)


@register_genre
class Jrock90sGenre(Genre):
    id = "jrock-90s"
    category = "style"
    display_name = "90s J-Rock"
    description = "90年代 J-ROCK 風。歪んだギターが前に出る速いビートとギターソロ、最後のサビで転調"
    description_en = "90s J-rock style: loud guitars over a fast beat, a guitar solo and a final key change"
    title = "J-Rock 90s"
    tempo_choices = (140, 146, 152, 158, 164, 168)

    instruments = {
        "kick": _inst("prog_kick", GmVoice(drum_note=36)),
        "snare": _inst("prog_snare", GmVoice(drum_note=38)),
        "hat": _inst("nostalgic_hihat", GmVoice(drum_note=42)),
        "crash": _inst("march_crash_cymbal", GmVoice(drum_note=49)),
        "bass": _inst("bass_pick", GmVoice(program=34)),
        "gtr": _inst("gtr_crunch", GmVoice(program=29), saturate=2.8),
        "lead": _inst("prog_lead_gtr", GmVoice(program=30)),
        "arp": _inst("gtr_clean_arp", GmVoice(program=27)),
        "line": _inst("orch_violin", GmVoice(program=48), volume=30),
    }
    harmony = Harmony(keys=(4, 9, 2), mode="aeolian", progressions=PROGRESSIONS, n_progressions=3)
    sections = {
        "intro": Section(prog=1, intensity=0.9, parts=frozenset({"lead", "bass", "drums", "guitars"}), fill=True, crash=True, motifs="chorus"),
        "a": Section(prog=1, intensity=0.7, parts=frozenset({"guitars", "lead", "bass", "drums"}), tags=frozenset({"clean"})),
        "b": Section(prog=2, intensity=0.85, parts=frozenset({"lead", "bass", "drums", "guitars"}), fill=True),
        "sabi": Section(intensity=1.0, parts=frozenset({"lead", "bass", "drums", "guitars"}), groove="drive", fill=True, crash=True, motifs="chorus"),
        "solo": Section(prog=1, intensity=0.95, parts=frozenset({"lead", "bass", "drums", "guitars"}), groove="drive", fill=True, motifs="solo"),
        "sabi_up": Section(intensity=1.0, parts=frozenset({"lead", "bass", "drums", "guitars"}), groove="drive", key_offset=1, crash=True, motifs="chorus"),
        "outro": Section(prog=1, intensity=0.9, parts=frozenset({"bass", "drums", "guitars"}), key_offset=1, crash=True),
    }
    form = ("intro", "a", "b", "sabi", "a", "b", "sabi", "solo", "sabi", "sabi_up", "outro")
    parts = (
        Part("drums", Groove(GROOVES), pan=128,
             kit=Kit(groups=(("kick/snare", ("kick", "snare")), ("cymbal", ("hat", "crash"))),
                     priority={"snare": 2, "crash": 3},
                     single_priority={"kick": 3, "snare": 4, "hat": 1, "crash": 2},
                     group_pan={"cymbal": 150})),
        Part("bass", BassLine("bass", kind="root8", vol=58), pan=128),
        Part("guitars", Guitars(PowerChop("gtr", 48, 40), Arp("arp", register=(19, 31), steps=(0, 2, 4, 6, 8, 10, 12, 14), vol=34)),
             pan=72, kit=Kit(groups=(("dist gtr", ("gtr",)), ("clean gtr", ("arp",))),
                              group_pan={"clean gtr": 96})),
        Part("lead", Lead("lead", ScaleRules(leap_probability=0.3, leap_semitones=(3, 5, 7)), LEAD_MOTIFS,
                   vol=48, gate=0.9, vibrato=0x46), pan=184),
        Part("lead echo", Echo(delay=3, ratio=0.45), follow="lead", pan=96, min_channels=8),
        Part("strings", Layer("line", vol=26, register=(19, 31)), follow="lead", pan=160, min_channels=8),
    )
    mod_channels = {4: 1, 6: 2, 8: 1}
