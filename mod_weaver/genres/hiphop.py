"""hiphop（旧 genres/hiphop.py の宣言を機械変換したもの。FRAMEWORK_REDESIGN.md §15）。"""
from __future__ import annotations

from ..core.composer import RhythmMotif, ScaleRules
from ..core.model import ChordSpec, GmVoice
from ..core.synth_presets import PRESETS
from ..framework.gens import BassLine, Comp, Groove, Layer, Lead, hits
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
    "main": hits("kick", (0, 7, 10), 60) + hits("snare", (4, 12), 52) + hits("hat", (0, 2, 4, 6, 8, 10, 12, 14), 22) + hits("kick", (15,), 44, 0.3),
    "sparse": hits("kick", (0, 10), 56) + hits("snare", (4, 12), 48),
}
LEAD_MOTIFS = {
    "hook": (RhythmMotif(rows=(0, 3, 6)), RhythmMotif(rows=(0, 3, 10)), RhythmMotif(rows=(0, 6, 8, 11))),
}
PROGRESSIONS = (
    ("i-VI", (C(0, "min", label="i"), C(8, "maj", label="VI"), C(0, "min", label="i"), C(8, "maj", label="VI"))),
    ("i-iv", (C(0, "min", label="i"), C(5, "min", label="iv"), C(0, "min", label="i"), C(5, "min", label="iv"))),
    ("im7-bVImaj7", (C(0, "m7", label="im7"), C(0, "m7", label="im7"), C(8, "maj7", label="bVImaj7"), C(8, "maj7", label="bVImaj7"))),
)


@register_genre
class HiphopGenre(Genre):
    id = "hiphop"
    display_name = "Hip Hop (Boom Bap)"
    description = "ヒップホップ。ラップが乗る余白を残したブーンバップのビートとサンプル風ループ"
    description_en = "Hip hop: boom-bap beats and sample-style loops that leave room for rap"
    title = "Boom Bap Cypher"
    tempo_choices = (86, 88, 90, 92, 94, 96)

    instruments = {
        "kick": _inst("drum_boombap_kick", GmVoice(drum_note=36)),
        "snare": _inst("drum_boombap_snare", GmVoice(drum_note=38)),
        "hat": _inst("nostalgic_hihat", GmVoice(drum_note=42)),
        "bass": _inst("bass_finger", GmVoice(program=33)),
        "horn": _inst("march_brass_horn", GmVoice(program=60)),
        "loop": _inst("keys_piano", GmVoice(program=0), volume=42),
        "str": _inst("orch_violin", GmVoice(program=48), volume=30),
    }
    harmony = Harmony(keys=(9, 4, 2, 7), mode="aeolian", progressions=PROGRESSIONS, n_progressions=1)
    sections = {
        "intro": Section(intensity=0.6, parts=frozenset({"comp", "drums"}), groove="sparse"),
        "verse": Section(intensity=0.75, parts=frozenset({"comp", "bass", "drums"})),
        "hook": Section(intensity=0.95, parts=frozenset({"comp", "bass", "drums", "lead"}), motifs="hook"),
        "outro": Section(intensity=0.6, parts=frozenset({"comp", "drums"}), groove="sparse"),
    }
    form = ("intro", "verse", "verse", "verse", "verse", "hook", "hook", "verse", "verse", "verse", "verse", "hook", "hook", "outro")
    parts = (
        Part("drums", Groove(GROOVES), pan=128,
             kit=Kit(groups=(("kick/snare", ("kick", "snare")), ("hat", ("hat",))),
                     priority={"snare": 3, "kick": 2},
                     single_priority={"kick": 2, "snare": 3, "hat": 1},
                     group_pan={"hat": 164})),
        Part("bass", BassLine("bass", kind="boombap", vol=56), pan=128),
        Part("comp", Comp("loop", kind="charleston", vol=40), pan=84),
        Part("lead", Lead("horn", ScaleRules(leap_probability=0.3, leap_semitones=(3, 5, 7)), LEAD_MOTIFS,
                   vol=46, gate=0.6), pan=172),
        Part("strings", Layer("str", vol=24, chordal=True), follow="lead", pan=100, min_channels=6),
    )
    swing = Swing(7, 5)
    mod_channels = {4: 2, 6: 1}
