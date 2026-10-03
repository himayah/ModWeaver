"""lofi-chill（旧 genres/lofi_chill.py の宣言を機械変換したもの。DESIGN.md §6）。"""
from __future__ import annotations

from ..core.composer import RhythmMotif, ScaleRules
from ..core.model import ChordSpec, GmVoice
from ..core.synth_presets import PRESETS
from ..framework.gens import BassLine, Comp, Echo, Fx, Groove, Layer, Lead, hits
from ..framework.genre import Genre, Harmony, Instrument, Kit, Part, Section, Sidechain
from ..framework.plan import Meter, Swing
from ..framework.registry import register_genre

C = ChordSpec


def _inst(key: str, gm: GmVoice, **changes) -> Instrument:
    patch = PRESETS[key]
    if changes:
        import dataclasses
        patch = dataclasses.replace(patch, **changes)
    return Instrument(patch=patch, gm=gm)

GROOVES = {
    "main": hits("kick", (0, 10), 58) + hits("rim", (4, 12), 40) + hits("shaker", (0, 2, 4, 6, 8, 10, 12, 14), 20) + hits("kick", (7,), 40, 0.4),
}
LEAD_MOTIFS = {
    "verse": (RhythmMotif(rows=(0, 4, 6, 12)), RhythmMotif(rows=(2, 6, 8, 12)), RhythmMotif(rows=(0, 3, 8, 10))),
}
PROGRESSIONS = (
    ("Imaj7-iii7-vi7-IVmaj7", (C(0, "maj7", label="Imaj7"), C(4, "m7", label="iii7"), C(9, "m7", label="vi7"), C(5, "maj7", label="IVmaj7"))),
    ("IVmaj7-ivm7-Imaj7-vi7", (C(5, "maj7", label="IVmaj7"), C(5, "m7", label="ivm7"), C(0, "maj7", label="Imaj7"), C(9, "m7", label="vi7"))),
    ("Imaj9-IVmaj9", (C(0, "maj9", label="Imaj9"), C(5, "maj9", label="IVmaj9"))),
)


@register_genre
class LofiChillGenre(Genre):
    id = "lofi-chill"
    category = "style"
    display_name = "Lo-fi Chill"
    description = "ローファイ・チル。柔らかいギターとフルート、うねるサイドチェインと雨音"
    description_en = "Lo-fi chill: soft guitar and flute, pumping sidechain and rain ambience"
    title = "Lo-fi Chill Rain"
    tempo_choices = (72, 76, 80, 84, 88)

    instruments = {
        "kick": _inst("drum_boombap_kick", GmVoice(drum_note=36)),
        "rim": _inst("drum_rim", GmVoice(drum_note=37)),
        "shaker": _inst("perc_shaker", GmVoice(drum_note=70)),
        "bass": _inst("bass_finger", GmVoice(program=33)),
        "lead": _inst("wind_flute", GmVoice(program=73), volume=36),
        "rain": _inst("fx_rain", GmVoice(program=122)),
        "ep": _inst("keys_ep", GmVoice(program=4), volume=36),
        "gtr": _inst("gtr_nylon", GmVoice(program=24)),
    }
    harmony = Harmony(keys=(0, 5, 7, 10), mode="ionian", progressions=PROGRESSIONS, n_progressions=2)
    sections = {
        "intro": Section(intensity=0.4, parts=frozenset({"comp", "fx"})),
        "a": Section(intensity=0.7, parts=frozenset({"comp", "lead", "fx", "drums", "bass"})),
        "b": Section(prog=1, intensity=0.7, parts=frozenset({"comp", "lead", "fx", "drums", "bass"})),
        "outro": Section(intensity=0.4, parts=frozenset({"comp", "fx"})),
    }
    form = ("intro", "a", "a", "b", "a", "outro")
    parts = (
        Part("drums", Groove(GROOVES), pan=128,
             kit=Kit(groups=(("kick/rim", ("kick", "rim")), ("shaker", ("shaker",))),
                     priority={"rim": 2},
                     single_priority={"kick": 3, "rim": 4, "shaker": 1},
                     group_pan={"shaker": 164})),
        Part("bass", BassLine("bass", kind="half", vol=54), pan=128),
        Part("comp", Comp("gtr", kind="half", vol=44, strum_ms=18.0), pan=84),
        Part("lead", Lead("lead", ScaleRules(leap_probability=0.2, leap_semitones=(3, 4, 5, 7)), LEAD_MOTIFS,
                   vol=40, gate=0.9, vibrato=0x32), pan=172),
        Part("fx", Fx("rain", every=2, vol=26), pan=128, min_channels=6),
        Part("flute echo", Echo(delay=3, ratio=0.45), follow="lead", pan=96, min_channels=8),
        Part("e.piano", Layer("ep", vol=30, register=(19, 31)), follow="lead", pan=160, min_channels=8),
    )
    swing = Swing(7, 5)
    mod_channels = {4: 1, 6: 2, 8: 1}
    mix = (Sidechain(triggers=("kick",), targets=("comp",), ratio=0.45, release_steps=3), Sidechain(triggers=("kick",), targets=("fx",), ratio=0.5, release_steps=3),)
