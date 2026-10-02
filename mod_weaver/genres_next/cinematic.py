"""cinematic（旧 genres/cinematic.py の宣言を機械変換したもの。FRAMEWORK_REDESIGN.md §15）。"""
# TODO(F6): 論理チャンネル ['viola', 'contrabass', 'horn', 'timpani'] を鳴らすパートが宣言に無い（上書きメソッドで鳴らす）
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
    "verse": (RhythmMotif(rows=(0, 8)), RhythmMotif(rows=(0, 6, 8)), RhythmMotif(rows=(0, 4, 8, 12)), RhythmMotif(rows=(0, 12))),
}
PROGRESSIONS = (
    ("i-VI-III-VII", (C(0, "min", label="i"), C(8, "maj", label="VI"), C(3, "maj", label="III"), C(10, "maj", label="VII"))),
    ("VI-VII-i", (C(8, "maj", label="VI"), C(10, "maj", label="VII"), C(0, "min", label="i"), C(0, "min", label="i"))),
    ("III-VII-i-VI (relative major I-V-vi-IV)", (C(3, "maj", label="III"), C(10, "maj", label="VII"), C(0, "min", label="i"), C(8, "maj", label="VI"))),
)


@register_genre
class CinematicGenre(Genre):
    id = "cinematic"
    display_name = "Cinematic"
    description = "映画音楽。ピアノのオスティナートから弦とホルンが重なり、ドラマチックに高まる"
    description_en = "Cinematic: piano ostinato building to soaring strings and horns"
    title = "Cinematic Rise"
    tempo_choices = (70, 72, 76, 80, 84)

    instruments = {
        "piano": _inst("keys_piano", GmVoice(program=0), volume=42),
        "vln": _inst("orch_violin", GmVoice(program=48)),
        "vc": _inst("orch_cello", GmVoice(program=42)),
        "cb": _inst("orch_bass_str", GmVoice(program=43)),
        "horn": _inst("march_brass_section", GmVoice(program=61), volume=40),
        "timp": _inst("orch_timpani", GmVoice(program=47)),
        "swell": _inst("free_cymbal_swell", GmVoice(program=119)),
        "vla": _inst("orch_viola", GmVoice(program=48), volume=34),
        "choir": _inst("vox_choir", GmVoice(program=52), volume=34),
    }
    harmony = Harmony(keys=(0, 2), mode="aeolian", progressions=PROGRESSIONS, n_progressions=2, fixed=True)
    sections = {
        "intro": Section(intensity=0.5, parts=frozenset({"arp"})),
        "rise1": Section(intensity=0.6, parts=frozenset({"viola", "bass", "arp"})),
        "theme": Section(intensity=0.75, parts=frozenset({"cb", "bass", "lead", "viola", "arp"})),
        "rise2": Section(prog=1, intensity=0.85, parts=frozenset({"bass", "horn", "pad", "timp", "viola", "lead", "cb", "arp"})),
        "climax": Section(prog=2, intensity=1.0, parts=frozenset({"bass", "horn", "pad", "timp", "viola", "lead", "cb", "arp"})),
        "resolve": Section(intensity=0.4, parts=frozenset({"arp"})),
    }
    form = ("intro", "rise1", "theme", "theme", "rise2", "climax", "climax", "resolve")
    parts = (
        Part("arp", Arp("piano", register=(12, 27), steps=(0, 2, 4, 6, 8, 10, 12, 14), vol=36, pattern="updown"), pan=100),
        Part("lead", Lead("vln", ScaleRules(leap_probability=0.3, leap_semitones=(3, 4, 5, 7, 8)), LEAD_MOTIFS,
                   vol=48, gate=1.0, vibrato=0x23), pan=84),
        # TODO: Part("viola", <ジェネレータ>, pan=160, min_channels=8)  ← 上書きメソッドで鳴らしていた
        Part("bass", BassLine("vc", kind="half", vol=46), pan=176),
        # TODO: Part("contrabass", <ジェネレータ>, pan=150, min_channels=8)  ← 上書きメソッドで鳴らしていた
        # TODO: Part("horn", <ジェネレータ>, pan=110)  ← 上書きメソッドで鳴らしていた
        Part("pad", Pad("choir", vol=34), pan=128),
        # TODO: Part("timpani", <ジェネレータ>, pan=128)  ← 上書きメソッドで鳴らしていた
    )
    mod_channels = {6: 1, 8: 2}
