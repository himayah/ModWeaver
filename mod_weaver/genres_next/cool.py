"""cool（旧 genres/cool.py の宣言を機械変換したもの。FRAMEWORK_REDESIGN.md §15）。"""
from __future__ import annotations

from ..core.composer import RhythmMotif, ScaleRules
from ..core.model import ChordSpec, GmVoice
from ..core.synth_presets import PRESETS
from ..framework.gens import BassLine, Echo, Groove, Layer, Lead, Pad, hits
from ..framework.genre import Genre, Harmony, Instrument, Kit, Part, Section
from ..framework.registry import register_genre

C = ChordSpec


def _inst(key: str, gm: GmVoice, **changes) -> Instrument:
    patch = PRESETS[key]
    if changes:
        import dataclasses
        patch = dataclasses.replace(patch, **changes)
    return Instrument(patch=patch, gm=gm)

GROOVES = {
    "main": hits("kick", (0, 10), 56) + hits("snare", (4, 12), 42) + hits("hat", (2, 6, 10, 14), 26) + hits("rim", (7, 13), 22, 0.6),
}
LEAD_MOTIFS = {
    "verse": (RhythmMotif(rows=(0, 3, 6)), RhythmMotif(rows=(0, 2, 8, 10)), RhythmMotif(rows=(4, 7, 12))),
}
PROGRESSIONS = (
    ("i9-IV9", (C(0, "m9", label="i9"), C(5, "dom9", label="IV9"))),
    ("i7-bVIImaj7-bVImaj7-v7", (C(0, "m7", label="i7"), C(10, "maj7", label="bVIImaj7"), C(8, "maj7", label="bVImaj7"), C(7, "m7", label="v7"))),
)


@register_genre
class CoolGenre(Genre):
    id = "cool"
    category = "mood"
    display_name = "Cool"
    description = "涼しげ。透明感のあるシンセと軽い2ステップのビート"
    description_en = "Cool: glassy synths over a light two-step beat"
    title = "Cool Night Air"
    tempo_choices = (100, 104, 108, 112)

    instruments = {
        "kick": _inst("drum_pop_kick", GmVoice(drum_note=36)),
        "snare": _inst("drum_rim", GmVoice(drum_note=37), volume=40),
        "hat": _inst("drum_909_hat", GmVoice(drum_note=42)),
        "rim": _inst("perc_clave", GmVoice(drum_note=75)),
        "bass": _inst("fb_sub", GmVoice(program=38)),
        "lead": _inst("syn_pluck", GmVoice(program=84)),
        "voice": _inst("vox_ooh", GmVoice(program=53), volume=30),
        "bell": _inst("keys_bell", GmVoice(program=9), volume=30),
        "pad": _inst("pad_glass", GmVoice(program=88)),
    }
    harmony = Harmony(keys=(6, 11, 1), mode="dorian", progressions=PROGRESSIONS, n_progressions=2)
    sections = {
        "intro": Section(intensity=0.5, parts=frozenset({"pad", "lead"})),
        "a": Section(intensity=0.8, parts=frozenset({"bass", "pad", "drums", "lead"})),
        "b": Section(prog=1, intensity=0.9, parts=frozenset({"bass", "pad", "drums", "lead"})),
        "break": Section(prog=1, intensity=0.5, parts=frozenset({"bass", "pad"})),
        "outro": Section(intensity=0.5, parts=frozenset({"pad", "lead"})),
    }
    form = ("intro", "a", "b", "break", "a", "b", "outro")
    parts = (
        Part("drums", Groove(GROOVES), pan=128,
             kit=Kit(groups=(("kick/snare", ("kick", "snare")), ("hat", ("hat", "rim"))),
                     priority={"snare": 2, "rim": 2},
                     single_priority={"kick": 3, "snare": 4, "hat": 1, "rim": 2},
                     group_pan={"hat": 164})),
        Part("bass", BassLine("bass", kind="half", vol=54), pan=128),
        Part("pad", Pad("pad", vol=30), pan=84),
        Part("lead", Lead("lead", ScaleRules(leap_probability=0.3, leap_semitones=(3, 5, 7)), LEAD_MOTIFS,
                   vol=42, gate=0.6), pan=150),
        Part("echo", Echo(delay=3, ratio=0.5, repeats=2), follow="lead", pan=100, min_channels=6),
        Part("voice", Layer("voice", vol=24, register=(19, 31)), follow="lead", pan=96, min_channels=8),
        Part("bell", Layer("bell", vol=22, register=(24, 35)), follow="lead", pan=160, min_channels=8),
    )
    mod_channels = {4: 1, 6: 2, 8: 1}
