"""synthwave（旧 genres/synthwave.py の宣言を機械変換したもの。DESIGN.md §6）。"""
from __future__ import annotations

from ..core.composer import RhythmMotif, ScaleRules
from ..core.model import ChordSpec, GmVoice
from ..core.synth_presets import PRESETS
from ..framework.gens import Arp, BassLine, Echo, Groove, Lead, Pad, hits
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
    "main": hits("kick", (0, 8), 60) + hits("snare", (4, 12), 54) + hits("hat", (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15), 20, 0.85),
}
LEAD_MOTIFS = {
    "verse": (RhythmMotif(rows=(0, 4, 6, 8, 12)), RhythmMotif(rows=(0, 6, 8, 10, 12))),
    "solo": (RhythmMotif(rows=(0, 2, 4, 6, 8, 10, 12, 14)), RhythmMotif(rows=(0, 3, 4, 6, 8, 11, 12))),
}
PROGRESSIONS = (
    ("i-VI-III-VII", (C(0, "min", label="i"), C(8, "maj", label="VI"), C(3, "maj", label="III"), C(10, "maj", label="VII"))),
    ("VI-VII-i-i", (C(8, "maj", label="VI"), C(10, "maj", label="VII"), C(0, "min", label="i"), C(0, "min", label="i"))),
    ("i-iv-VI-V", (C(0, "min", label="i"), C(5, "min", label="iv"), C(8, "maj", label="VI"), C(7, "maj", label="V"))),
)


@register_genre
class SynthwaveGenre(Genre):
    id = "synthwave"
    display_name = "Synthwave / Retrowave"
    description = "シンセウェイブ。80年代のシンセとゲートスネア、8分で脈打つベース"
    description_en = "Synthwave: 80s synths, gated snare and a pulsing eighth-note bass"
    title = "Synthwave Drive"
    tempo_choices = (96, 100, 104, 108, 112)

    instruments = {
        "kick": _inst("drum_pop_kick", GmVoice(drum_note=36)),
        "snare": _inst("drum_gated_snare", GmVoice(drum_note=40)),
        "hat": _inst("nostalgic_hihat", GmVoice(drum_note=42)),
        "bass": _inst("bass_synth_saw", GmVoice(program=38)),
        "lead": _inst("syn_saw_lead", GmVoice(program=81)),
        "arp": _inst("syn_arp_bell", GmVoice(program=98)),
        "pad": _inst("syn_poly_pad", GmVoice(program=90)),
    }
    harmony = Harmony(keys=(9, 4, 6), mode="aeolian", progressions=PROGRESSIONS, n_progressions=2)
    sections = {
        "intro": Section(intensity=0.6, parts=frozenset({"arp", "pad"})),
        "verse": Section(intensity=0.8, parts=frozenset({"arp", "lead", "drums", "bass", "pad"})),
        "chorus": Section(prog=1, intensity=1.0, parts=frozenset({"arp", "lead", "drums", "bass", "pad"})),
        "solo": Section(prog=2, intensity=0.9, parts=frozenset({"arp", "lead", "drums", "bass", "pad"}), motifs="solo"),
        "outro": Section(intensity=0.5, parts=frozenset({"arp", "bass", "pad"})),
    }
    form = ("intro", "verse", "chorus", "verse", "chorus", "solo", "chorus", "outro")
    parts = (
        Part("drums", Groove(GROOVES), pan=128,
             kit=Kit(groups=(("kick/snare", ("kick", "snare")), ("hat", ("hat",))),
                     priority={"snare": 2},
                     single_priority={"kick": 3, "snare": 4, "hat": 1},
                     group_pan={"hat": 164})),
        Part("bass", BassLine("bass", kind="octave8", vol=52), pan=128),
        Part("pad", Pad("pad", vol=30), pan=80),
        Part("lead", Lead("lead", ScaleRules(leap_semitones=(3, 5, 7)), LEAD_MOTIFS,
                   vol=44, gate=0.9, vibrato=0x44), pan=150),
        Part("arp", Arp("arp", register=(24, 35), steps=(0, 2, 4, 6, 8, 10, 12, 14), vol=30, pattern="updown"), pan=190, min_channels=6),
        Part("lead echo", Echo(delay=3, ratio=0.45), follow="lead", pan=96, min_channels=8),
        Part("arp echo", Echo(delay=3, ratio=0.45), follow="arp", pan=160, min_channels=8),
    )
    mod_channels = {4: 1, 6: 2, 8: 1}
