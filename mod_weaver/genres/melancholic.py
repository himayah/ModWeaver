"""melancholic（旧 genres/melancholic.py の宣言を機械変換したもの。DESIGN.md §6）。"""
from __future__ import annotations

from ..core.composer import RhythmMotif, ScaleRules
from ..core.model import ChordSpec, GmVoice
from ..core.synth_presets import PRESETS
from ..framework.gens import Arp, BassLine, Lead, Pad
from ..framework.genre import Genre, Harmony, Instrument, Kit, Part, Section
from ..framework.registry import register_genre

C = ChordSpec


def _inst(key: str, gm: GmVoice, **changes) -> Instrument:
    patch = PRESETS[key]
    if changes:
        import dataclasses
        patch = dataclasses.replace(patch, **changes)
    return Instrument(patch=patch, gm=gm)

LEAD_MOTIFS = {
    "verse": (RhythmMotif(rows=(0, 8)), RhythmMotif(rows=(0, 4, 8)), RhythmMotif(rows=(0, 6, 8, 12)), RhythmMotif(rows=(0, 4, 12))),
}
PROGRESSIONS = (
    ("i-VI-III-VII", (C(0, "min", label="i"), C(8, "maj", label="VI"), C(3, "maj", label="III"), C(10, "maj", label="VII"))),
    ("i-iv-VII-III", (C(0, "min", label="i"), C(5, "min", label="iv"), C(10, "maj", label="VII"), C(3, "maj", label="III"))),
    ("i-VII-VI-V", (C(0, "min", label="i"), C(10, "maj", label="VII"), C(8, "maj", label="VI"), C(7, "maj", label="V"))),
)


@register_genre
class MelancholicGenre(Genre):
    id = "melancholic"
    category = "mood"
    display_name = "Melancholic"
    description = "物悲しい。短調のピアノが旋律を歌い、弦のパッドが支える"
    description_en = "Melancholic piano ballad in a minor key over soft strings"
    title = "Grey Winter"
    tempo_choices = (66, 68, 70, 72, 74, 76)

    instruments = {
        "piano": _inst("keys_piano", GmVoice(program=0)),
        "accomp": _inst("keys_piano", GmVoice(program=0), name="PianoAccomp", volume=38),
        "cello": _inst("orch_cello", GmVoice(program=42)),
        "str": _inst("orch_violin", GmVoice(program=48), name="StringPad", volume=34),
    }
    harmony = Harmony(keys=(9, 2, 4), mode="aeolian", progressions=PROGRESSIONS, n_progressions=2)
    sections = {
        "intro": Section(intensity=0.4, parts=frozenset({"arp"})),
        "a": Section(intensity=0.6, parts=frozenset({"arp", "bass", "lead"})),
        "b": Section(prog=1, intensity=0.8, parts=frozenset({"arp", "bass", "pad", "lead"})),
        "outro": Section(intensity=0.4, parts=frozenset({"arp", "pad"})),
    }
    form = ("intro", "a", "b", "a", "b", "outro")
    parts = (
        Part("lead", Lead("piano", ScaleRules(leap_probability=0.3, leap_semitones=(3, 4, 5, 7, 8)), LEAD_MOTIFS,
                   vol=48, gate=1.0), pan=128),
        Part("arp", Arp("accomp", register=(12, 24), steps=(0, 2, 4, 6, 8, 10, 12, 14), vol=34, pattern="updown"), pan=128),
        Part("pad", Pad("str", vol=30), pan=128),
        Part("bass", BassLine("cello", kind="half", vol=40), pan=128),
    )
    mod_channels = {4: 1}
