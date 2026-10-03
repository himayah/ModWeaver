"""tango（アルゼンチン・タンゴ風。NEW_GENRES_DESIGN.md §14.4）。

4拍をはっきり刻むマルカート、3-3-2 のアクセント、ヴァイオリンの旋律（アラストレ＝下からの引きずり）、
バンドネオンの和音、和声的短音階、終わりの「チャン・チャン」。
"""
from __future__ import annotations

from ..core.composer import RhythmMotif, ScaleRules
from ..core.model import ChordSpec, GmVoice
from ..core.pitch import CHORD_QUALITIES, fold_into_range
from ..framework.context import Generator, MeasureCtx
from ..framework.gens import Groove, Pad, hits
from ..framework.genre import Genre, Harmony, Kit, Part, Section
from ..framework.registry import register_genre
from ._ornament import OrnamentedLead, WithTempo, inst as _inst

C = ChordSpec

GROOVES = {
    "main": hits("bombo", (0, 4, 8, 12), 48) + hits("clave", (0, 6, 12), 30),
}
LEAD_MOTIFS = {
    "verse": (RhythmMotif(rows=(0, 6, 12)), RhythmMotif(rows=(0, 3, 6, 8, 12)), RhythmMotif(rows=(0, 4, 6, 10, 12))),
    "strong": (RhythmMotif(rows=(0, 3, 6, 9, 12)), RhythmMotif(rows=(0, 2, 3, 6, 8, 12, 14)), RhythmMotif(rows=(0, 6, 8, 12))),
}
PROGRESSIONS = (
    ("i-iv-V7-i", (C(0, "min", label="i"), C(5, "min", label="iv"), C(7, "dom7", label="V7"), C(0, "min", label="i"))),
    ("i-bVI-V7-i", (C(0, "min", label="i"), C(8, "maj", label="bVI"), C(7, "dom7", label="V7"), C(0, "min", label="i"))),
    ("i-V7-i-iv", (C(0, "min", label="i"), C(7, "dom7", label="V7"), C(0, "min", label="i"), C(5, "min", label="iv"))),
)


class Marcato(Generator):
    """コントラバスの4拍（根音と5度を交互に）。"""

    def measure(self, m: MeasureCtx) -> None:
        reg = m.genre.harmony.registers.bass
        fifth = fold_into_range(m.m.chord.bass + 7, *reg)
        for i, step in enumerate((0, 4, 8, 12)):
            m.note(step, "bass", m.m.chord.bass if i % 2 == 0 else fifth, vel=m.scale_vol(54 if i % 2 == 0 else 44), dur=3)


class Bandoneon(Generator):
    """バンドネオンの和音: 3-3-2（0・6・12）。終わりの小節は「チャン・チャン」（0 と 6 を強く）。"""

    inst = "bandoneon"

    def measure(self, m: MeasureCtx) -> None:
        shape = CHORD_QUALITIES[m.m.quality]
        if m.plan.kind == "outro" and m.is_last:
            for step in (0, 6):
                m.note(step, "bandoneon", m.m.chord.harmony, vel=62, chord=shape, dur=4)
            return
        for i, step in enumerate((0, 6, 12)):
            m.note(step, "bandoneon", m.m.chord.harmony, vel=m.scale_vol(40 if i == 0 else 34), chord=shape, dur=4)


class PianoBeats(Generator):
    inst = "piano"

    def measure(self, m: MeasureCtx) -> None:
        shape = CHORD_QUALITIES[m.m.quality]
        for step in (0, 4, 8, 12):
            m.note(step, "piano", m.m.chord.harmony, vel=m.scale_vol(34 if step % 8 == 0 else 26), chord=shape, dur=2)


def _sec(parts, *, prog=0, intensity=0.8, measures=8, motifs="verse") -> Section:
    return Section(prog=prog, measures=measures, intensity=intensity, parts=frozenset(parts), motifs=motifs)


@register_genre
class TangoGenre(Genre):
    id = "tango"
    category = "genre"
    display_name = "Tango"
    description = "アルゼンチン・タンゴ風。マルカートの4拍、3-3-2 のアクセント、アラストレのヴァイオリン、バンドネオン、チャン・チャンの終止"
    description_en = "Argentine tango style: marcato four, 3-3-2 accents, dragging violin, bandoneon chords and a chan-chan ending"
    title = "Tango Nocturne"
    tempo_choices = (112, 116, 120, 124, 128, 132)

    instruments = {
        "bombo": _inst("perc_surdo", GmVoice(drum_note=41)),
        "clave": _inst("perc_clave", GmVoice(drum_note=75)),
        "bass": _inst("swing_walk_bass", GmVoice(program=32), volume=50),
        "bandoneon": _inst("ru_bayan", GmVoice(program=23), name="Bandoneon", volume=38),
        "violin": _inst("orch_violin", GmVoice(program=40), name="TangoViolin", volume=46),
        "piano": _inst("keys_piano", GmVoice(program=0), volume=34),
        "strings": _inst("orch_violin", GmVoice(program=48), name="Strings", volume=26),
    }
    harmony = Harmony(keys=(9, 2, 4, 7), mode="harmonic_minor", progressions=PROGRESSIONS, n_progressions=2)
    _band = {"drums", "bass", "bando", "lead"}
    sections = {
        "intro": _sec({"drums", "bass", "bando"}, intensity=0.6, measures=4),
        "a": _sec(_band | {"piano"}, intensity=0.8),
        "b": _sec(_band | {"piano", "strings"}, prog=1, intensity=0.95, motifs="strong"),
        "outro": _sec({"drums", "bass", "bando", "lead"}, intensity=0.7, measures=4),
    }
    form = ("intro", "a", "a", "b", "a", "b", "outro")
    parts = (
        Part("drums", Groove(GROOVES), pan=128,
             kit=Kit(groups=(("bombo", ("bombo",)), ("clave", ("clave",))), priority={"bombo": 2, "clave": 1},
                     single_priority={"bombo": 2, "clave": 1}, group_pan={"clave": 168})),
        Part("bass", Marcato(), pan=128),
        Part("bando", WithTempo(Bandoneon(), lambda sp: (1.0, 0.8) if sp.name == "outro" else (1.0, 1.0)), pan=84),
        Part("lead", OrnamentedLead("violin", ScaleRules(leap_probability=0.15, leap_semitones=(3, 4, 5)), LEAD_MOTIFS,
                                    vol=46, gate=0.7, vibrato=0x34, scoop=0.4, grace=0.2), pan=172),
        Part("piano", PianoBeats(), pan=100, min_channels=6),
        Part("strings", Pad("strings", vol=26), pan=128, min_channels=6),
    )
    mod_channels = {4: 1, 6: 2}
