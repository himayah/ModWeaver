"""jazz（旧 genres/jazz.py の宣言を機械変換したもの。DESIGN.md §6）。"""
from __future__ import annotations

from ..core.composer import RhythmMotif, ScaleRules
from ..core.model import ChordSpec, GmVoice
from ..core.synth_presets import PRESETS
from ..framework.gens import BassLine, Comp, Groove, Lead, hits
from ..framework.genre import Genre, Harmony, Instrument, Kit, Part, Section
from ..framework.plan import Meter, Swing
from ..core.pitch import CHORD_QUALITIES
from ..framework.score import NoteEvent
from ..framework.registry import register_genre

C = ChordSpec


def _inst(key: str, gm: GmVoice, **changes) -> Instrument:
    patch = PRESETS[key]
    if changes:
        import dataclasses
        patch = dataclasses.replace(patch, **changes)
    return Instrument(patch=patch, gm=gm)

GROOVES = {
    "main": hits("ride", (0, 2, 4, 6), 34) + hits("ride", (3, 7), 24) + hits("brush", (2, 6), 26, 0.8),
    "fill": hits("brush", (4, 5, 6, 7), 32),
}
LEAD_MOTIFS = {
    "head": (RhythmMotif(rows=(0, 4)), RhythmMotif(rows=(0, 3, 4)), RhythmMotif(rows=(1, 4, 6))),
    "solo": (RhythmMotif(rows=(0, 1, 2, 4, 5, 6)), RhythmMotif(rows=(0, 2, 3, 4, 6, 7)), RhythmMotif(rows=(1, 2, 3, 5, 6))),
}
METER = Meter(8, 2, (4, 4))
PROGRESSIONS = (
    ("i11 vamp", (C(0, "quartal", label="i11"), C(0, "quartal", label="i11"), C(0, "quartal", label="i11"), C(2, "quartal", label="ii11"))),
)


FERMATA = 6                                    # coda でこの小節の頭に最後の長い和音を置き、以降は余韻だけ


def place_fermata(sec, score) -> None:
    """coda: 前半は head の素材、FERMATA の小節で全員が長い和音を伸ばして終わる（旧 compose_measure の上書き）。
    トランペットは最後の小節の4 step 目で止める。"""
    if sec.kind != "coda":
        return
    fer, last = sec.measures[FERMATA], sec.measures[-1]
    score.mute(tuple(score.parts), fer.start, sec.steps)
    chord = fer.chord
    score.add("drums", NoteEvent(fer.start, "ride", None, 40))
    score.add("bass", NoteEvent(fer.start, "bass", chord.bass, 50))
    score.add("comp", NoteEvent(fer.start, "piano", chord.harmony, 42, chord=CHORD_QUALITIES[fer.quality]))
    score.add("lead", NoteEvent(fer.start, "tpt", chord.chord_tones[len(chord.chord_tones) // 2], 40,
                                  dur=last.start + 4 - fer.start))


@register_genre
class JazzGenre(Genre):
    id = "jazz"
    display_name = "Modal Jazz"
    description = "ジャズ。ドリアンのモーダルなヴァンプ、4度堆積のピアノとミュート・トランペット"
    description_en = "Modal jazz: dorian vamps, quartal piano voicings and muted trumpet"
    title = "Modal Jazz"
    tempo_choices = (120, 126, 132, 138, 144)

    instruments = {
        "ride": _inst("swing_ride", GmVoice(drum_note=51)),
        "brush": _inst("swing_brush_snare", GmVoice(drum_note=38)),
        "bass": _inst("swing_walk_bass", GmVoice(program=32)),
        "tpt": _inst("orch_trumpet", GmVoice(program=59), name="MuteTrumpet", volume=38),
        "piano": _inst("keys_piano", GmVoice(program=0), volume=40),
    }
    harmony = Harmony(keys=(2,), mode="dorian", progressions=PROGRESSIONS, n_progressions=1)
    sections = {
        "head_a": Section(intensity=0.7, parts=frozenset({"lead", "bass", "drums", "comp"}), motifs="head", meter=METER, measures=8),
        "head_b": Section(intensity=0.8, parts=frozenset({"lead", "bass", "drums", "comp"}), key_offset=1, fill=True, motifs="head", meter=METER, measures=8),
        "solo_a": Section(intensity=0.9, parts=frozenset({"lead", "bass", "drums", "comp"}), motifs="solo", meter=METER, measures=8),
        "solo_b": Section(intensity=1.0, parts=frozenset({"lead", "bass", "drums", "comp"}), key_offset=1, fill=True, motifs="solo", meter=METER, measures=8),
        "coda": Section(intensity=0.6, parts=frozenset({"lead", "bass", "drums", "comp"}), motifs="head", meter=METER, measures=8),
    }
    form = ("head_a", "head_a", "head_b", "head_a", "solo_a", "solo_a", "solo_b", "solo_a", "head_a", "head_a", "head_b", "coda")
    parts = (
        Part("drums", Groove(GROOVES), pan=128,
             kit=Kit(groups=(("ride/brush", ("ride", "brush")),),
                     priority={"brush": 2})),
        Part("bass", BassLine("bass", kind="walking", vol=54), pan=128),
        Part("comp", Comp("piano", kind="charleston", vol=38), pan=128),
        Part("lead", Lead("tpt", ScaleRules(leap_probability=0.3, leap_semitones=(3, 4, 5, 7), dissonance_weight=0.1), LEAD_MOTIFS,
                   vol=46, gate=0.95, vibrato=0x23), pan=128),
    )
    swing = Swing(14, 10)

    def finalize_section(self, sec, score, rng) -> None:
        place_fermata(sec, score)
    mod_channels = {4: 1}
