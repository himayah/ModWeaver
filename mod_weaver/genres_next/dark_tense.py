"""dark-tense（旧 genres/dark_tense.py の宣言を機械変換したもの。FRAMEWORK_REDESIGN.md §15）。"""
# TODO(F6): 論理チャンネル ['braam', 'fx'] を鳴らすパートが宣言に無い（上書きメソッドで鳴らす）
from __future__ import annotations

from ..core.model import ChordSpec, GmVoice
from ..core.synth_presets import PRESETS
from ..framework.gens import BassLine, Echo, Groove, Layer, Pad, hits
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
    "main": hits("taiko", (0, 8), 60) + hits("tick", (0, 4, 8, 12), 28) + hits("tick", (1, 2, 3, 5, 6, 7, 9, 10, 11, 13, 14, 15), 18),
    "tick": hits("tick", (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15), 18),
}
PROGRESSIONS = (
    ("i-bII-i-V", (C(0, "min", label="i"), C(1, "maj", label="bII"), C(0, "min", label="i"), C(7, "maj", label="V"))),
    ("i-VI-iv-V", (C(0, "min", label="i"), C(8, "maj", label="VI"), C(5, "min", label="iv"), C(7, "maj", label="V"))),
)


@register_genre
class DarkTenseGenre(Genre):
    id = "dark-tense"
    category = "mood"
    display_name = "Dark / Tense"
    description = "緊張感。低音のオスティナートと刻むパルス、重い打撃"
    description_en = "Dark and tense: low ostinato, ticking pulse and heavy hits"
    title = "Dark Pulse"
    tempo_choices = (90, 92, 94, 96, 98, 100)

    instruments = {
        "taiko": _inst("perc_taiko", GmVoice(program=116)),
        "tick": _inst("drum_909_hat", GmVoice(drum_note=42)),
        "bass": _inst("bass_synth_saw", GmVoice(program=38)),
        "str": _inst("tension_strings", GmVoice(program=49)),
        "braam": _inst("brass_braam", GmVoice(program=61)),
        "riser": _inst("fx_riser", GmVoice(program=97)),
        "impact": _inst("fx_impact", GmVoice(program=55)),
        "choir": _inst("vox_choir", GmVoice(program=52), volume=30),
    }
    harmony = Harmony(keys=(0, 2), mode="harmonic_minor", progressions=PROGRESSIONS, n_progressions=2)
    sections = {
        "intro": Section(intensity=0.4, parts=frozenset({"pad", "drums"}), groove="tick"),
        "build": Section(intensity=0.6, parts=frozenset({"fx", "pad", "bass", "drums"}), groove="tick"),
        "pulse": Section(prog=1, intensity=0.8, parts=frozenset({"pad", "bass", "drums", "lead"})),
        "climax": Section(intensity=1.0, parts=frozenset({"bass", "drums", "pad", "lead", "fx"})),
        "collapse": Section(intensity=0.4, parts=frozenset({"pad"})),
    }
    form = ("intro", "build", "pulse", "build", "climax", "collapse")
    parts = (
        Part("drums", Groove(GROOVES), pan=128,
             kit=Kit(groups=(("taiko", ("taiko",)), ("tick", ("tick",))),
                     single_priority={"taiko": 4, "tick": 1},
                     group_pan={"tick": 176})),
        Part("bass", BassLine("bass", kind="pulse16", vol=46), pan=128),
        Part("pad", Pad("str", vol=34, chordal=False), pan=72),
        # TODO: Part("braam", <ジェネレータ>, pan=110)  ← 上書きメソッドで鳴らしていた
        # TODO: Part("fx", <ジェネレータ>, pan=150, min_channels=6)  ← 上書きメソッドで鳴らしていた
        Part("choir", Layer("choir", vol=26, chordal=True), follow="lead", pan=96, min_channels=8),
        Part("braam echo", Echo(delay=4, ratio=0.45), follow="braam", pan=160, min_channels=8),
    )
    mod_channels = {4: 1, 6: 2, 8: 1}
