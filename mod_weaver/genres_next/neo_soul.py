"""neo-soul（旧 genres/neo_soul.py の宣言を機械変換したもの。FRAMEWORK_REDESIGN.md §15）。"""
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
    "main": hits("kick", (0, 3, 10), 58) + hits("kick", (7,), 44, 0.5) + hits("snare", (4, 12), 48) + hits("hat", (0, 2, 4, 6, 8, 10, 12, 14), 26) + hits("hat", (5, 13), 16, 0.5) + hits("rim", (15,), 22, 0.5),
}
LEAD_MOTIFS = {
    "verse": (RhythmMotif(rows=(1, 4, 6, 9, 12)), RhythmMotif(rows=(0, 3, 6, 10, 13)), RhythmMotif(rows=(2, 5, 8, 11, 14))),
    "chorus": (RhythmMotif(rows=(0, 3, 4, 8, 11, 12)), RhythmMotif(rows=(0, 2, 6, 8, 12))),
}
PROGRESSIONS = (
    ("IVmaj9-iii7-vi9", (C(3, "maj9", label="bIIImaj9"), C(2, "m7", label="ii7"), C(5, "m9", label="iv9"), C(0, "m11", label="i11"))),
    ("ii9-V13-iii7-VI7", (C(2, "m9", label="ii9"), C(7, "dom13", label="V13"), C(4, "m7", label="iii7"), C(9, "dom9", label="VI9"))),
    ("i11-IV9", (C(0, "m11", label="i11"), C(5, "dom9", label="IV9"))),
)


@register_genre
class NeoSoulGenre(Genre):
    id = "neo-soul"
    category = "style"
    display_name = "Neo Soul"
    description = "ネオソウル風。よれたビートとエレピ主体の豊かなテンションコード"
    description_en = "Neo soul style: laid-back off-grid beats and lush electric piano chords"
    title = "Neo Soul Groove"
    tempo_choices = (80, 84, 88, 92, 96)

    instruments = {
        "kick": _inst("drum_boombap_kick", GmVoice(drum_note=36)),
        "snare": _inst("drum_pop_snare", GmVoice(drum_note=38)),
        "hat": _inst("nostalgic_hihat", GmVoice(drum_note=42)),
        "rim": _inst("drum_rim", GmVoice(drum_note=37)),
        "bass": _inst("bass_finger", GmVoice(program=33)),
        "lead": _inst("vox_ooh", GmVoice(program=53)),
        "gtr": _inst("gtr_clean_arp", GmVoice(program=27), volume=34),
        "ep": _inst("keys_ep", GmVoice(program=4)),
    }
    harmony = Harmony(keys=(3, 8, 5), mode="dorian", progressions=PROGRESSIONS, n_progressions=2)
    sections = {
        "intro": Section(prog=1, intensity=0.5, parts=frozenset({"comp", "pad"})),
        "verse": Section(intensity=0.7, parts=frozenset({"comp", "lead", "drums", "bass", "pad"})),
        "chorus": Section(prog=1, intensity=0.9, parts=frozenset({"comp", "lead", "drums", "bass", "pad"}), motifs="chorus"),
        "bridge": Section(intensity=0.6, parts=frozenset({"comp", "bass", "drums"})),
        "outro": Section(prog=1, intensity=0.5, parts=frozenset({"comp", "bass", "pad"})),
    }
    form = ("intro", "verse", "chorus", "verse", "chorus", "bridge", "chorus", "outro")
    parts = (
        Part("drums", Groove(GROOVES, late={"snare": 0.35, "hat": 0.25}), pan=128,
             kit=Kit(groups=(("kick/snare", ("kick", "snare")), ("hat", ("hat", "rim"))),
                     priority={"snare": 2, "rim": 2},
                     single_priority={"kick": 3, "snare": 4, "hat": 1, "rim": 2},
                     group_pan={"hat": 164})),
        Part("bass", BassLine("bass", kind="synco16", vol=56), pan=128),
        Part("comp", Comp("ep", kind="stab2", vol=42, wobble=35), pan=84),
        Part("lead", Lead("lead", ScaleRules(leap_semitones=(3, 4, 5, 7), dissonance_weight=0.12), LEAD_MOTIFS,
                   vol=46, gate=0.9, vibrato=0x42), pan=150),
        Part("pad", Pad("ep", vol=30), pan=180, min_channels=6),
        Part("vocal echo", Echo(delay=3, ratio=0.45), follow="lead", pan=96, min_channels=8),
        Part("guitar", Layer("gtr", vol=30, register=(19, 31)), follow="lead", pan=160, min_channels=8),
    )
    swing = Swing(8, 4)
    mod_channels = {4: 1, 6: 2, 8: 1}
