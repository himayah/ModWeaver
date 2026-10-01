"""pop を新フレームワークへ試験移植したもの（FRAMEWORK_REDESIGN.md §15.1・§15.2 のグループA）。

F3 の試験移植その1。旧 ``mod_weaver/genres/pop.py``（``PopProfile``）の宣言をそのまま写す。本番の
``mod_weaver/genres/`` には置かない（旧 ``GenreProfile`` 版と id が同じだが、レジストリが別なので
衝突しない。F6 で本番に昇格させるときに置き場所を変える）。
"""
from __future__ import annotations

from mod_weaver.core.composer import RhythmMotif, ScaleRules
from mod_weaver.core.model import ChordSpec, GmVoice
from mod_weaver.core.synth_presets import PRESETS
from mod_weaver.framework.gens import BassLine, Comp, Echo, Groove, Layer, Pad, hits
from mod_weaver.framework.gens.lead import Lead
from mod_weaver.framework.genre import Genre, Harmony, Instrument, Kit, Part, Section

C = ChordSpec


def _inst(key: str, gm: GmVoice, **changes) -> Instrument:
    patch = PRESETS[key]
    if changes:
        import dataclasses
        patch = dataclasses.replace(patch, **changes)
    return Instrument(patch=patch, gm=gm)


MAIN = (hits("kick", (0, 8, 10), 58) + hits("snare", (4, 12), 50)
        + hits("hat", range(0, 16, 2), 30) + hits("shaker", (1, 3, 5, 7, 9, 11, 13, 15), 18, 0.5))
VERSE = hits("kick", (0, 10), 54) + hits("snare", (4, 12), 44) + hits("shaker", range(0, 16, 2), 22)
FILL = hits("snare", (8, 10, 12, 13, 14, 15), 46)
CRASH = hits("crash", (0,), 54)
GROOVES = {"main": MAIN, "verse": VERSE, "fill": FILL, "crash": CRASH}

LEAD_MOTIFS = {
    "verse": (RhythmMotif((0, 4, 6, 8, 12)), RhythmMotif((2, 4, 8, 10, 12)), RhythmMotif((0, 3, 6, 8, 11))),
    "chorus": (RhythmMotif((0, 2, 4, 8, 10, 12)), RhythmMotif((0, 4, 6, 8, 12, 14)), RhythmMotif((0, 2, 6, 8, 12))),
}

PROGRESSIONS = (
    ("I-V-vi-IV", (C(0, "maj", label="I"), C(7, "maj", label="V"), C(9, "min", label="vi"),
                   C(5, "maj", label="IV"))),
    ("vi-IV-I-V", (C(9, "min", label="vi"), C(5, "maj", label="IV"), C(0, "maj", label="I"),
                   C(7, "maj", label="V"))),
    ("I-vi-IV-V", (C(0, "maj", label="I"), C(9, "min", label="vi"), C(5, "maj", label="IV"),
                   C(7, "maj", label="V"))),
    ("IV-V-iii-vi", (C(5, "maj7", label="IVmaj7"), C(7, "maj", label="V"), C(4, "m7", label="iii7"),
                     C(9, "min", label="vi"))),
)
BASE = frozenset({"drums", "bass", "comp", "pad"})


class PopToy(Genre):
    id = "pop"
    display_name = "Pop"
    description = "ポップ。長調の明るいメロディとピアノ、覚えやすいサビ"
    description_en = "Pop: bright major-key melodies, piano and a catchy chorus"
    title = "Bright Pop"
    tempo_choices = (100, 104, 108, 112, 116, 120)

    instruments = {
        "kick": _inst("drum_pop_kick", GmVoice(drum_note=36)),
        "snare": _inst("drum_pop_snare", GmVoice(drum_note=38)),
        "hat": _inst("nostalgic_hihat", GmVoice(drum_note=42)),
        "shaker": _inst("perc_shaker", GmVoice(drum_note=70)),
        "crash": _inst("march_crash_cymbal", GmVoice(drum_note=49)),
        "bass": _inst("bass_finger", GmVoice(program=33)),
        "piano": _inst("keys_piano", GmVoice(program=0)),
        "pad": _inst("pad_warm", GmVoice(program=89)),
        "lead": _inst("vox_ooh", GmVoice(program=53)),
        "line": _inst("orch_violin", GmVoice(program=48), volume=30),
    }
    harmony = Harmony(keys=(0, 2, 5, 7), mode="ionian", progressions=PROGRESSIONS, n_progressions=3)
    sections = {
        "intro": Section(prog=0, intensity=0.4, parts=frozenset({"comp", "pad"})),
        "verse": Section(prog=1, intensity=0.6, parts=BASE | {"lead"}, groove="verse"),
        "pre": Section(prog=2, intensity=0.7, parts=BASE | {"lead"}, fill=True),
        "chorus": Section(prog=0, intensity=1.0, parts=BASE | {"lead"}, crash=True, fill=True, motifs="chorus"),
        "bridge": Section(prog=2, intensity=0.5, parts=frozenset({"bass", "comp", "pad", "lead"})),
        "chorus_up": Section(prog=0, intensity=1.0, parts=BASE | {"lead"}, key_offset=1, crash=True,
                              motifs="chorus"),
        "outro": Section(prog=0, intensity=0.4, parts=frozenset({"comp", "pad", "bass"})),
    }
    form = ("intro", "verse", "pre", "chorus", "verse", "pre", "chorus", "bridge", "chorus", "chorus_up", "outro")
    parts = (
        Part("drums", Groove(GROOVES), pan=128,
             kit=Kit(groups=(("kick_snare", ("kick", "snare")), ("hat", ("hat", "shaker", "crash"))),
                     priority={"snare": 2, "crash": 3, "hat": 2},
                     single_priority={"snare": 4, "kick": 3, "crash": 2},
                     group_pan={"hat": 160})),
        Part("bass", BassLine("bass", kind="root8", vol=54), pan=128),
        Part("comp", Comp("piano", kind="pulse8", vol=40), pan=88),
        Part("lead", Lead("lead", ScaleRules(leap_probability=0.2, leap_semitones=(3, 4, 5, 7)), LEAD_MOTIFS,
                           vol=50, gate=0.85, vibrato=0x32), pan=168),
        Part("pad", Pad("pad", vol=28), pan=64, min_channels=6),
        Part("lead echo", Echo(delay=3, ratio=0.45), follow="lead", pan=96, min_channels=8),
        Part("strings", Layer("line", vol=26, register=(19, 31)), follow="lead", pan=160, min_channels=8),
    )
    mod_channels = {4: 1, 6: 1, 8: 1}
