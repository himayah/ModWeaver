"""house（旧 genres/house.py の宣言を機械変換したもの。DESIGN.md §6）。"""
from __future__ import annotations

from ..core.model import ChordSpec, GmVoice
from ..core.synth_presets import PRESETS
from ..framework.gens import BassLine, Comp, Echo, Groove, Layer, Pad, hits
from ..framework.genre import Genre, Harmony, Instrument, Kit, Part, Section, Sidechain
from ..framework.registry import register_genre

C = ChordSpec


def _inst(key: str, gm: GmVoice, **changes) -> Instrument:
    patch = PRESETS[key]
    if changes:
        import dataclasses
        patch = dataclasses.replace(patch, **changes)
    return Instrument(patch=patch, gm=gm)

GROOVES = {
    "main": hits("kick", (0, 4, 8, 12), 60) + hits("clap", (4, 12), 42) + hits("ohat", (2, 6, 10, 14), 28) + hits("shaker", (1, 3, 5, 7, 9, 11, 13, 15), 18, 0.8) + hits("rim", (7, 15), 24, 0.5),
    "drums": hits("kick", (0, 4, 8, 12), 58) + hits("ohat", (2, 6, 10, 14), 24),
}
PROGRESSIONS = (
    ("im7-IV9", (C(0, "m7", label="im7"), C(5, "dom9", label="IV9"))),
    ("im9-bVIImaj7", (C(0, "m9", label="im9"), C(10, "maj7", label="bVIImaj7"))),
    ("im7-iv7-bVIImaj7-bIIImaj7", (C(0, "m7", label="im7"), C(5, "m7", label="iv7"), C(10, "maj7", label="bVIImaj7"), C(3, "maj7", label="bIIImaj7"))),
)


@register_genre
class HouseGenre(Genre):
    id = "house"
    display_name = "House / Deep House"
    description = "ハウス。4つ打ちの安定したグルーヴと裏拍のオルガン・スタブ"
    description_en = "House: steady four-on-the-floor groove with offbeat organ stabs"
    title = "Deep House"
    tempo_choices = (118, 120, 122, 124)

    instruments = {
        "kick": _inst("drum_909_kick", GmVoice(drum_note=36)),
        "clap": _inst("fb_clap", GmVoice(drum_note=39)),
        "ohat": _inst("drum_909_open_hat", GmVoice(drum_note=46)),
        "rim": _inst("drum_rim", GmVoice(drum_note=37)),
        "shaker": _inst("perc_shaker", GmVoice(drum_note=70)),
        "bass": _inst("bass_deep", GmVoice(program=38)),
        "chop": _inst("fb_vocal_chop", GmVoice(program=53), volume=34),
        "stab": _inst("keys_house_stab", GmVoice(program=16)),
        "pad": _inst("pad_warm", GmVoice(program=89)),
    }
    harmony = Harmony(keys=(9, 2, 7), mode="dorian", progressions=PROGRESSIONS, n_progressions=2)
    sections = {
        "intro": Section(intensity=0.6, parts=frozenset({"drums"}), groove="drums"),
        "groove": Section(intensity=0.8, parts=frozenset({"comp", "bass", "drums"})),
        "main": Section(prog=1, intensity=1.0, parts=frozenset({"comp", "bass", "pad", "drums"})),
        "break": Section(prog=2, intensity=0.5, parts=frozenset({"comp", "pad"})),
        "outro": Section(intensity=0.6, parts=frozenset({"bass", "drums"}), groove="drums"),
    }
    form = ("intro", "groove", "main", "main", "break", "main", "main", "outro")
    parts = (
        Part("drums", Groove(GROOVES), pan=128,
             kit=Kit(groups=(("kick", ("kick",)), ("clap/hat", ("clap", "ohat", "rim")), ("shaker", ("shaker",))),
                     priority={"clap": 3, "rim": 2},
                     single_priority={"kick": 4, "clap": 3, "ohat": 1, "rim": 2, "shaker": 1},
                     group_pan={"clap/hat": 150, "shaker": 184})),
        Part("bass", BassLine("bass", kind="house", vol=56), pan=128),
        Part("comp", Comp("stab", kind="offbeat", vol=40), pan=96),
        Part("pad", Pad("pad", vol=28), pan=64),
        Part("stab echo", Echo(delay=3, ratio=0.45), follow="comp", pan=96, min_channels=8),
        Part("vocal chop", Layer("chop", vol=26, register=(19, 31)), follow="comp", pan=160, min_channels=8),
    )
    mod_channels = {4: 1, 6: 2, 8: 1}
    mix = (Sidechain(triggers=("kick",), targets=("pad",), ratio=0.5, release_steps=3),)
