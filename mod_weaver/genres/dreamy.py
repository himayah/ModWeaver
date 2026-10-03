"""dreamy（旧 genres/dreamy.py の宣言を機械変換したもの。DESIGN.md §6）。"""
from __future__ import annotations

from ..core.composer import RhythmMotif, ScaleRules
from ..core.model import ChordSpec, GmVoice
from ..core.synth_presets import PRESETS
from ..framework.gens import Arp, BassLine, Echo, Groove, Layer, Lead, Pad, hits
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
    "main": hits("kick", (0, 10), 44) + hits("rim", (8,), 34),
}
LEAD_MOTIFS = {
    "verse": (RhythmMotif(rows=(0, 8)), RhythmMotif(rows=(0, 6, 12)), RhythmMotif(rows=(4, 12))),
}
PROGRESSIONS = (
    ("Imaj7-IVmaj7", (C(0, "maj7", label="Imaj7"), C(5, "maj7", label="IVmaj7"))),
    ("I-iii-IV-iv", (C(0, "add9", label="Iadd9"), C(4, "m7", label="iii7"), C(5, "maj7", label="IVmaj7"), C(5, "m6", label="ivm6"))),
)


@register_genre
class DreamyGenre(Genre):
    id = "dreamy"
    category = "mood"
    display_name = "Dreamy"
    description = "夢見心地。深い残響感のアルペジオとパッド"
    description_en = "Dreamy: echoing arpeggios over lush pads"
    title = "Dreamy Haze"
    tempo_choices = (80, 84, 88, 92)

    instruments = {
        "kick": _inst("drum_pop_kick", GmVoice(drum_note=36), volume=44),
        "rim": _inst("drum_rim", GmVoice(drum_note=37)),
        "bass": _inst("fb_sub", GmVoice(program=38)),
        "arp": _inst("syn_arp_bell", GmVoice(program=98)),
        "lead": _inst("wind_flute", GmVoice(program=73), volume=36),
        "voice": _inst("vox_ooh", GmVoice(program=53), volume=30),
        "pad": _inst("pad_glass", GmVoice(program=88)),
    }
    harmony = Harmony(keys=(3, 8, 1), mode="lydian", progressions=PROGRESSIONS, n_progressions=2)
    sections = {
        "intro": Section(intensity=0.5, parts=frozenset({"arp", "pad"})),
        "a": Section(intensity=0.7, parts=frozenset({"arp", "lead", "drums", "bass", "pad"})),
        "b": Section(prog=1, intensity=0.8, parts=frozenset({"arp", "lead", "drums", "bass", "pad"})),
        "outro": Section(intensity=0.4, parts=frozenset({"arp", "pad"})),
    }
    form = ("intro", "a", "b", "a", "b", "outro")
    parts = (
        Part("drums", Groove(GROOVES), pan=128,
             kit=Kit(groups=(("kick/rim", ("kick", "rim")),),
                     priority={"rim": 2})),
        Part("bass", BassLine("bass", kind="whole", vol=50), pan=128),
        Part("pad", Pad("pad", vol=32), pan=72),
        Part("arp", Arp("arp", register=(24, 35), steps=(0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15), vol=30, pattern="updown"), pan=176),
        Part("arp echo", Echo(delay=3, ratio=0.5, repeats=2), follow="arp", pan=80, min_channels=6),
        Part("lead", Lead("lead", ScaleRules(leap_probability=0.3, leap_semitones=(4, 5, 7)), LEAD_MOTIFS,
                   vol=36, gate=0.95, vibrato=0x32), pan=150, min_channels=6),
        Part("flute echo", Echo(delay=3, ratio=0.45), follow="lead", pan=96, min_channels=8),
        Part("voice", Layer("voice", vol=24, register=(19, 31)), follow="lead", pan=160, min_channels=8),
    )
    mod_channels = {4: 1, 6: 2, 8: 1}
