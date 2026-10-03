"""rnb-soul（旧 genres/rnb_soul.py の宣言を機械変換したもの。DESIGN.md §6）。"""
from __future__ import annotations

from ..core.composer import RhythmMotif, ScaleRules
from ..core.model import ChordSpec, GmVoice
from ..core.synth_presets import PRESETS
from ..framework.gens import BassLine, Comp, Echo, Groove, Layer, Lead, Pad, hits
from ..framework.genre import Genre, Harmony, Instrument, Kit, Part, Section
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
    "main": hits("kick", (0, 7, 10), 54) + hits("snare", (4, 12), 46) + hits("hat", (0, 2, 4, 6, 8, 10, 12, 14), 24) + hits("rim", (15,), 20, 0.4),
    "fill": hits("snare", (12, 14, 15), 40),
}
LEAD_MOTIFS = {
    "verse": (RhythmMotif(rows=(0, 3, 4, 8, 11, 12)), RhythmMotif(rows=(2, 4, 6, 10, 12)), RhythmMotif(rows=(0, 6, 8, 9, 12))),
    "chorus": (RhythmMotif(rows=(0, 4, 6, 8, 12)), RhythmMotif(rows=(0, 2, 3, 4, 8, 12))),
}
PROGRESSIONS = (
    ("IVmaj7-iii7-ii7-Imaj7", (C(5, "maj7", label="IVmaj7"), C(4, "m7", label="iii7"), C(2, "m7", label="ii7"), C(0, "maj7", label="Imaj7"))),
    ("ii9-V13-Imaj9-Imaj9", (C(2, "m9", label="ii9"), C(7, "dom13", label="V13"), C(0, "maj9", label="Imaj9"), C(0, "maj9", label="Imaj9"))),
    ("vi9-ii9-V7sus4-Imaj9", (C(9, "m9", label="vi9"), C(2, "m9", label="ii9"), C(7, "7sus4", label="V7sus4"), C(0, "maj9", label="Imaj9"))),
)


@register_genre
class RnbSoulGenre(Genre):
    id = "rnb-soul"
    display_name = "R&B / Soul"
    description = "R&B／ソウル。滑らかなテンションコードと歌うような旋律のスロー・ジャム"
    description_en = "R&B / soul: smooth extended chords and a singing melody in a slow jam"
    title = "Soul Slow Jam"
    tempo_choices = (68, 72, 76, 80, 84)

    instruments = {
        "kick": _inst("drum_pop_kick", GmVoice(drum_note=36)),
        "snare": _inst("drum_pop_snare", GmVoice(drum_note=38)),
        "hat": _inst("nostalgic_hihat", GmVoice(drum_note=42)),
        "rim": _inst("drum_rim", GmVoice(drum_note=37)),
        "bass": _inst("bass_finger", GmVoice(program=33)),
        "lead": _inst("vox_ooh", GmVoice(program=53)),
        "flute": _inst("wind_flute", GmVoice(program=73), volume=30),
        "ep": _inst("keys_ep", GmVoice(program=4)),
        "str": _inst("pad_warm", GmVoice(program=89)),
    }
    harmony = Harmony(keys=(3, 8, 1), mode="ionian", progressions=PROGRESSIONS, n_progressions=3)
    sections = {
        "intro": Section(prog=1, intensity=0.5, parts=frozenset({"comp", "pad"})),
        "verse": Section(intensity=0.6, parts=frozenset({"comp", "lead", "drums", "bass", "pad"})),
        "pre": Section(prog=2, intensity=0.7, parts=frozenset({"comp", "lead", "drums", "bass", "pad"}), fill=True),
        "chorus": Section(prog=1, intensity=0.9, parts=frozenset({"comp", "lead", "drums", "bass", "pad"}), fill=True, motifs="chorus"),
        "bridge": Section(prog=2, intensity=0.6, parts=frozenset({"comp", "bass", "pad", "lead"})),
        "outro": Section(prog=1, intensity=0.5, parts=frozenset({"comp", "bass", "pad"})),
    }
    form = ("intro", "verse", "pre", "chorus", "verse", "pre", "chorus", "bridge", "chorus", "outro")
    parts = (
        Part("drums", Groove(GROOVES), pan=128,
             kit=Kit(groups=(("kick/snare", ("kick", "snare")), ("hat", ("hat", "rim"))),
                     priority={"snare": 2, "rim": 2},
                     single_priority={"kick": 3, "snare": 4, "hat": 1, "rim": 2},
                     group_pan={"hat": 160})),
        Part("bass", BassLine("bass", kind="boombap", vol=56), pan=128),
        Part("comp", Comp("ep", kind="half", vol=40, wobble=34), pan=88),
        Part("lead", Lead("lead", ScaleRules(leap_probability=0.2, leap_semitones=(3, 4, 5), dissonance_weight=0.1), LEAD_MOTIFS,
                   vol=48, gate=0.95, vibrato=0x43), pan=140),
        Part("pad", Pad("str", vol=26), pan=60, min_channels=6),
        Part("vocal echo", Echo(delay=3, ratio=0.45), follow="lead", pan=96, min_channels=8),
        Part("flute", Layer("flute", vol=26, register=(19, 31)), follow="lead", pan=160, min_channels=8),
    )
    swing = Swing(7, 5)
    mod_channels = {4: 1, 6: 2, 8: 1}
