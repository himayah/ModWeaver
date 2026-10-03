"""energetic（旧 genres/energetic.py の宣言を機械変換したもの。DESIGN.md §6）。"""
from __future__ import annotations

from ..core.composer import RhythmMotif, ScaleRules
from ..core.model import ChordSpec, GmVoice
from ..core.synth_presets import PRESETS
from ..framework.gens import BassLine, Echo, Groove, Layer, Lead, hits
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
    "main": hits("kick", (0, 6, 8, 14), 60) + hits("snare", (4, 12), 56) + hits("hat", (0, 2, 4, 6, 8, 10, 12, 14), 34),
    "half": hits("kick", (0, 10), 58) + hits("snare", (8,), 56) + hits("hat", (0, 2, 4, 6, 8, 10, 12, 14), 28),
    "fill": hits("tom", (8, 9, 10, 11), 52, 1.0, notes=(29, 27, 24, 20)) + hits("snare", (12, 13, 14, 15), 54),
    "crash": hits("crash", (0,), 60),
}
LEAD_MOTIFS = {
    "verse": (RhythmMotif(rows=(0, 2, 4, 8, 10, 12)), RhythmMotif(rows=(0, 4, 6, 8, 12, 14))),
    "chorus": (RhythmMotif(rows=(0, 4, 8, 12)), RhythmMotif(rows=(0, 2, 4, 6, 8, 12))),
}
PROGRESSIONS = (
    ("I-V-vi-IV", (C(0, "maj", label="I"), C(7, "maj", label="V"), C(9, "min", label="vi"), C(5, "maj", label="IV"))),
    ("IV-I-V-vi", (C(5, "maj", label="IV"), C(0, "maj", label="I"), C(7, "maj", label="V"), C(9, "min", label="vi"))),
    ("I-IV-vi-V", (C(0, "maj", label="I"), C(5, "maj", label="IV"), C(9, "min", label="vi"), C(7, "maj", label="V"))),
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


@register_genre
class EnergeticGenre(Genre):
    id = "energetic"
    category = "mood"
    display_name = "Energetic"
    description = "元気・活動的。速いテンポと強いドラム、8分で刻むギターとベース"
    description_en = "Energetic: fast, drum-driven rock with driving guitars and bass"
    title = "Energetic Run"
    tempo_choices = (160, 164, 168, 172, 176)

    instruments = {
        "kick": _inst("prog_kick", GmVoice(drum_note=36)),
        "snare": _inst("prog_snare", GmVoice(drum_note=38)),
        "hat": _inst("nostalgic_hihat", GmVoice(drum_note=42)),
        "crash": _inst("march_crash_cymbal", GmVoice(drum_note=49)),
        "tom": _inst("drum_tom", GmVoice(drum_note=45)),
        "bass": _inst("bass_pick", GmVoice(program=34)),
        "gtr": _inst("gtr_crunch", GmVoice(program=29)),
        "lead": _inst("syn_square_lead", GmVoice(program=80)),
        "sbrass": _inst("syn_brass", GmVoice(program=62), volume=30),
    }
    harmony = Harmony(keys=(4, 9, 2), mode="ionian", progressions=PROGRESSIONS, n_progressions=2)
    sections = {
        "intro": Section(intensity=0.8, parts=frozenset({"bass", "drums", "comp"}), fill=True, crash=True),
        "verse": Section(prog=1, intensity=0.8, parts=frozenset({"lead", "bass", "drums", "comp"}), fill=True),
        "pre": Section(prog=2, intensity=0.9, parts=frozenset({"lead", "bass", "drums", "comp"}), fill=True),
        "chorus": Section(intensity=1.0, parts=frozenset({"lead", "bass", "drums", "comp"}), fill=True, crash=True, motifs="chorus"),
        "bridge": Section(prog=2, intensity=0.7, parts=frozenset({"lead", "bass", "drums", "comp"}), groove="half"),
        "outro": Section(intensity=0.9, parts=frozenset({"bass", "drums", "comp"}), crash=True),
    }
    form = ("intro", "verse", "pre", "chorus", "verse", "pre", "chorus", "bridge", "chorus", "chorus", "outro")
    parts = (
        Part("drums", Groove(GROOVES), pan=128,
             kit=Kit(groups=(("kick/snare", ("kick", "snare")), ("cymbal", ("hat", "crash")), ("tom", ("tom",))),
                     priority={"snare": 2, "crash": 3},
                     single_priority={"kick": 3, "snare": 4, "hat": 1, "crash": 2, "tom": 3},
                     group_pan={"cymbal": 150, "tom": 110})),
        Part("bass", BassLine("bass", kind="root8", vol=58), pan=128),
        Part("comp", PowerChop("gtr", 46, 38), pan=76),
        Part("lead", Lead("lead", ScaleRules(leap_semitones=(4, 5, 7)), LEAD_MOTIFS,
                   vol=46, gate=0.8), pan=180),
        Part("lead echo", Echo(delay=3, ratio=0.45), follow="lead", pan=96, min_channels=8),
        Part("synth brass", Layer("sbrass", vol=26), follow="lead", pan=160, min_channels=8),
    )
    mod_channels = {4: 1, 6: 2, 8: 1}
