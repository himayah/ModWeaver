"""rock（旧 genres/rock.py の宣言を機械変換したもの。DESIGN.md §6）。"""
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
    "main": hits("kick", (0, 8, 10), 60) + hits("snare", (4, 12), 54) + hits("hat", (0, 2, 4, 6, 8, 10, 12, 14), 32),
    "ride": hits("kick", (0, 8, 10), 60) + hits("snare", (4, 12), 56) + hits("ride", (0, 2, 4, 6, 8, 10, 12, 14), 34),
    "fill": hits("tom", (8, 10), 50, 1.0, notes=(27, 21)) + hits("snare", (12, 13, 14, 15), 50),
    "crash": hits("crash", (0,), 58),
}
LEAD_MOTIFS = {
    "verse": (RhythmMotif(rows=(0, 4, 6, 8, 12)), RhythmMotif(rows=(0, 2, 6, 10, 12)), RhythmMotif(rows=(0, 6, 8, 12, 14))),
    "chorus": (RhythmMotif(rows=(0, 4, 8, 12)), RhythmMotif(rows=(0, 2, 4, 8, 12, 14))),
    "solo": (RhythmMotif(rows=(0, 2, 3, 4, 6, 8, 10, 11, 12, 14)), RhythmMotif(rows=(0, 1, 2, 4, 6, 7, 8, 12, 14))),
}
PROGRESSIONS = (
    ("I-bVII-IV-I", (C(0, "maj", label="I"), C(10, "maj", label="bVII"), C(5, "maj", label="IV"), C(0, "maj", label="I"))),
    ("I-IV-V-IV", (C(0, "maj", label="I"), C(5, "maj", label="IV"), C(7, "maj", label="V"), C(5, "maj", label="IV"))),
    ("i-bVI-bVII-i", (C(0, "min", label="i"), C(8, "maj", label="bVI"), C(10, "maj", label="bVII"), C(0, "min", label="i"))),
)


class RockRiff(Generator):
    """パワーコードのリフ: 根音を8分で刻み、2小節ごとに5度・短7度へ動く（ミクソリディアンのリフ。旧 comp）。"""

    def __init__(self, inst: str) -> None:
        self.inst = inst

    def measure(self, m: MeasureCtx) -> None:
        root = m.m.chord.harmony
        top = m.genre.harmony.registers.harmony[1] + 10
        riff = (0, 0, 0, 0, 7, 7, 10, 7) if m.m.index % 2 else (0, 0, 0, 0, 0, 0, 3, 5)
        for i, step in enumerate(range(0, min(16, m.m.steps), 2)):
            note = root + riff[i] if root + riff[i] <= top else root
            m.note(step, self.inst, note, vel=m.scale_drum(46 if i % 4 == 0 else 38))


@register_genre
class RockGenre(Genre):
    id = "rock"
    display_name = "Rock"
    description = "ロック。ギターのリフと8ビート、4/4 の中〜速いテンポ"
    description_en = "Rock: guitar riffs over a straight eight-beat"
    title = "Rock Anthem"
    tempo_choices = (112, 116, 120, 124, 128, 132)

    instruments = {
        "kick": _inst("prog_kick", GmVoice(drum_note=36)),
        "snare": _inst("prog_snare", GmVoice(drum_note=38)),
        "hat": _inst("nostalgic_hihat", GmVoice(drum_note=42)),
        "ride": _inst("swing_ride", GmVoice(drum_note=51)),
        "crash": _inst("march_crash_cymbal", GmVoice(drum_note=49)),
        "tom": _inst("drum_tom", GmVoice(drum_note=45)),
        "bass": _inst("bass_pick", GmVoice(program=34)),
        "gtr": _inst("gtr_crunch", GmVoice(program=29)),
        "lead": _inst("prog_lead_gtr", GmVoice(program=30)),
        "organ": _inst("keys_organ", GmVoice(program=16), volume=30),
    }
    harmony = Harmony(keys=(4, 9, 2), mode="mixolydian", progressions=PROGRESSIONS, n_progressions=2)
    sections = {
        "intro": Section(intensity=0.7, parts=frozenset({"drums", "comp"}), crash=True),
        "verse": Section(intensity=0.7, parts=frozenset({"lead", "bass", "drums", "comp"}), fill=True),
        "chorus": Section(prog=1, intensity=1.0, parts=frozenset({"lead", "bass", "drums", "comp"}), groove="ride", fill=True, crash=True, motifs="chorus"),
        "solo": Section(intensity=0.9, parts=frozenset({"lead", "bass", "drums", "comp"}), fill=True, motifs="solo"),
        "outro": Section(intensity=0.8, parts=frozenset({"bass", "drums", "comp"}), crash=True),
    }
    form = ("intro", "verse", "chorus", "verse", "chorus", "solo", "chorus", "outro")
    parts = (
        Part("drums", Groove(GROOVES), pan=128,
             kit=Kit(groups=(("kick/snare", ("kick", "snare")), ("cymbal", ("hat", "ride", "crash")), ("tom", ("tom",))),
                     priority={"snare": 2, "crash": 3},
                     single_priority={"kick": 3, "snare": 4, "hat": 1, "ride": 1, "crash": 2, "tom": 3},
                     group_pan={"cymbal": 150, "tom": 110})),
        Part("bass", BassLine("bass", kind="root8", vol=56), pan=128),
        Part("comp", RockRiff("gtr"), pan=72),
        Part("lead", Lead("lead", ScaleRules(leap_probability=0.3, leap_semitones=(3, 5, 7), dissonance_weight=0.05), LEAD_MOTIFS,
                   vol=48, gate=0.9, vibrato=0x44), pan=184),
        Part("lead echo", Echo(delay=3, ratio=0.45), follow="lead", pan=96, min_channels=8),
        Part("organ", Layer("organ", vol=26), follow="lead", pan=160, min_channels=8),
    )
    mod_channels = {4: 1, 6: 2, 8: 1}
