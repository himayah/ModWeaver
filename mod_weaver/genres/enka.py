"""enka（演歌。NEW_GENRES_DESIGN.md §6）。

ヨナ抜き短音階の旋律にしゃくり・こぶしを付け、ストリングスと爪弾くギター、間奏の箏、歌の切れ目の三味線の合いの手、
最後のサビで全音上げの転調。ボーカルは含まない。
"""
from __future__ import annotations

from ..core.composer import RhythmMotif, ScaleRules
from ..core.model import ChordSpec, GmVoice
from ..framework.context import Generator, MeasureCtx
from ..framework.gens import Arp, BassLine, Groove, Pad, Sing, hits
from ..framework.genre import Genre, Harmony, Kit, Part, Section, Voice
from ..framework.registry import register_genre
from ._ornament import OrnamentedLead, inst as _inst

C = ChordSpec

GROOVES = {
    "main": hits("kick", (0, 8), 48) + hits("brush", (4, 12), 36) + hits("rim", (14,), 20, 0.5),
}
LEAD_MOTIFS = {
    "verse": (RhythmMotif(rows=(0, 8)), RhythmMotif(rows=(0, 6, 8)), RhythmMotif(rows=(0, 4, 8, 12))),
    "chorus": (RhythmMotif(rows=(0, 4, 8, 12)), RhythmMotif(rows=(0, 6, 8, 12)), RhythmMotif(rows=(0, 4, 6, 8, 12))),
}
PROGRESSIONS = (
    ("i-iv-V7-i", (C(0, "min", label="i"), C(5, "min", label="iv"), C(7, "dom7", label="V7"), C(0, "min", label="i"))),
    ("i-VI-VII-i", (C(0, "min", label="i"), C(8, "maj", label="VI"), C(10, "maj", label="VII"), C(0, "min", label="i"))),
    ("i-iv-i-V7", (C(0, "min", label="i"), C(5, "min", label="iv"), C(0, "min", label="i"), C(7, "dom7", label="V7"))),
    ("i-VI-iv-V7", (C(0, "min", label="i"), C(8, "maj", label="VI"), C(5, "min", label="iv"), C(7, "dom7", label="V7"))),
)


class Aizuchi(Generator):
    """歌の切れ目（区間の最後の小節の後半）に、三味線が音階を下る短い合いの手を入れる。"""

    def measure(self, m: MeasureCtx) -> None:
        if not m.is_last:
            return
        tones = sorted(m.m.chord.scale_tones)
        top = max((i for i, t in enumerate(tones) if t <= 31), default=len(tones) - 1)
        for k, step in enumerate((10, 12, 14)):
            m.note(step, "shamisen", tones[max(0, top - 2 * k)], vel=m.scale_vol(40 - 4 * k))


def _sec(parts, *, prog=0, intensity=0.8, measures=8, motifs="verse", key_offset=0) -> Section:
    return Section(prog=prog, measures=measures, intensity=intensity, parts=frozenset(parts), motifs=motifs,
                   key_offset=key_offset)


@register_genre
class EnkaGenre(Genre):
    id = "enka"
    category = "genre"
    display_name = "Enka"
    description = "演歌。ヨナ抜き短音階、しゃくり・こぶし、ストリングスと爪弾くギター、合いの手、最後のサビで転調（歌は含まない）"
    description_en = "Enka: pentatonic minor melody with scoops and kobushi, strings, plucked guitar, shamisen fills, final-chorus key change (a sung part with --voice)"
    title = "Enka Ballad"
    tempo_choices = (68, 72, 76, 80, 84, 88)

    instruments = {
        "kick": _inst("drum_pop_kick", GmVoice(drum_note=36)),
        "brush": _inst("swing_brush_snare", GmVoice(drum_note=38)),
        "rim": _inst("drum_rim", GmVoice(drum_note=37)),
        "bass": _inst("bass_finger", GmVoice(program=33)),
        "gtr": _inst("gtr_nylon", GmVoice(program=24), volume=38),
        "violin": _inst("orch_violin", GmVoice(program=40), name="EnkaViolin", volume=46),
        "strings": _inst("orch_violin", GmVoice(program=48), name="EnkaStrings", volume=28),
        "shamisen": _inst("jp_shamisen", GmVoice(program=106)),
        "koto": _inst("jp_koto", GmVoice(program=107)),
        "voice": Voice(GmVoice(program=54), timbre="female", volume=46),     # --voice で歌う（旋律は lead と同じ）
    }
    harmony = Harmony(keys=(9, 4, 2, 11), mode="minor_pent", progressions=PROGRESSIONS, n_progressions=2)
    _core = {"drums", "bass", "comp", "lead"}
    sections = {
        "intro": _sec({"comp", "strings", "bass"}, intensity=0.5, measures=4),
        "verse": _sec(_core | {"strings", "aizuchi", "vocal"}, intensity=0.65),
        "bridge": _sec(_core | {"strings", "aizuchi", "vocal"}, prog=1, intensity=0.75),
        "chorus": _sec(_core | {"strings", "aizuchi", "vocal"}, prog=1, intensity=0.9, motifs="chorus"),
        "interlude": _sec(_core | {"strings", "koto"}, intensity=0.8, motifs="chorus"),
        "chorus2": _sec(_core | {"strings", "aizuchi", "vocal"}, prog=1, intensity=1.0, motifs="chorus", key_offset=2),
        "outro": _sec({"comp", "strings", "lead", "bass"}, intensity=0.5, measures=4),
    }
    form = ("intro", "verse", "bridge", "chorus", "interlude", "verse", "chorus", "chorus2", "outro")
    parts = (
        Part("drums", Groove(GROOVES), pan=128,
             kit=Kit(groups=(("kick/brush", ("kick", "brush")), ("rim", ("rim",))),
                     priority={"kick": 3, "brush": 2}, single_priority={"kick": 3, "brush": 2, "rim": 1})),
        Part("bass", BassLine("bass", kind="rootfifth", vol=48), pan=128),
        Part("comp", Arp("gtr", (12, 28), tuple(range(0, 16, 2)), vol=34), pan=84),
        Part("lead", OrnamentedLead("violin", ScaleRules(leap_probability=0.12, leap_semitones=(3, 5, 7)), LEAD_MOTIFS,
                                    vol=46, gate=0.95, vibrato=0x44, scoop=0.5, kobushi=0.4), pan=172),
        Part("strings", Pad("strings", vol=28), pan=128, min_channels=6),
        Part("aizuchi", Aizuchi(), pan=60, min_channels=8),
        Part("koto", Arp("koto", (19, 31), tuple(range(0, 16, 2)), vol=36), pan=70, min_channels=8),
        Part("vocal", Sing("voice"), pan=128, depends=("lead",), min_channels=6, requires=frozenset({"voice"}),
             ducks=("lead",), duck_ratio=0.35),
    )
    mod_channels = {4: 1, 6: 2, 8: 1}
