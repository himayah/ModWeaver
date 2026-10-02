"""techno（旧 genres/techno.py の宣言を機械変換したもの。FRAMEWORK_REDESIGN.md §15）。"""
# TODO(F6): 論理チャンネル ['sequence'] を鳴らすパートが宣言に無い（上書きメソッドで鳴らす）
from __future__ import annotations

from ..core.model import ChordSpec, GmVoice
from ..core.synth_presets import PRESETS
from ..framework.gens import BassLine, Groove, hits
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
    "main": hits("kick", (0, 4, 8, 12), 60) + hits("ohat", (2, 6, 10, 14), 30) + hits("clap", (4, 12), 40),
    "hats": hits("kick", (0, 4, 8, 12), 60) + hits("hat", (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15), 22, 0.7) + hits("ohat", (2, 6, 10, 14), 28),
    "kick": hits("kick", (0, 4, 8, 12), 58),
}
PROGRESSIONS = (
    ("i7", (C(0, "m7", label="i7"),)),
    ("i7-bVII", (C(0, "m7", label="i7"), C(10, "maj", label="bVII"))),
)


@register_genre
class TechnoGenre(Genre):
    id = "techno"
    display_name = "Minimal Techno"
    description = "テクノ。繰り返しの中で少しずつ変わるシーケンスと4つ打ち"
    description_en = "Minimal techno: a hypnotic four-on-the-floor with slowly mutating sequences"
    title = "Minimal Techno"
    tempo_choices = (124, 126, 128, 130, 132)

    instruments = {
        "kick": _inst("drum_909_kick", GmVoice(drum_note=36)),
        "hat": _inst("drum_909_hat", GmVoice(drum_note=42)),
        "ohat": _inst("drum_909_open_hat", GmVoice(drum_note=46)),
        "clap": _inst("fb_clap", GmVoice(drum_note=39)),
        "bass": _inst("bass_synth_square", GmVoice(program=39)),
        "seq": _inst("syn_stab", GmVoice(program=62)),
    }
    harmony = Harmony(keys=(9, 2), mode="aeolian", progressions=PROGRESSIONS, n_progressions=1)
    sections = {
        "k1": Section(intensity=0.6, parts=frozenset({"drums"}), groove="kick"),
        "k2": Section(intensity=0.7, parts=frozenset({"bass", "drums"}), groove="kick"),
        "h1": Section(intensity=0.8, parts=frozenset({"bass", "drums", "comp"}), groove="hats"),
        "f1": Section(intensity=1.0, parts=frozenset({"bass", "drums", "comp"})),
        "f2": Section(intensity=1.0, parts=frozenset({"bass", "drums", "comp"})),
        "b1": Section(intensity=0.6, parts=frozenset({"bass", "comp"})),
        "f3": Section(intensity=1.0, parts=frozenset({"bass", "drums", "comp"})),
        "o1": Section(intensity=0.6, parts=frozenset({"drums"}), groove="hats"),
    }
    form = ("k1", "k2", "h1", "f1", "f2", "h1", "b1", "f3", "f2", "f3", "o1", "k1")
    parts = (
        Part("drums", Groove(GROOVES), pan=128,
             kit=Kit(groups=(("kick", ("kick",)), ("hats/clap", ("hat", "ohat", "clap"))),
                     priority={"clap": 3, "ohat": 2})),
        Part("bass", BassLine("bass", kind="offbeat", vol=48), pan=128),
        # TODO: Part("sequence", <ジェネレータ>, pan=128)  ← 上書きメソッドで鳴らしていた
    )
    mod_channels = {4: 1}
