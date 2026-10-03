"""klezmer（クレズマー風。NEW_GENRES_DESIGN.md §14.3）。

2/4 のオン・パッ（チューバとアコーディオン）に、フリギア・ドミナント／ウクライナ・ドリアンのクラリネット旋律
（すすり泣き＝しゃくりと装飾）。ドイナ風のゆっくりした導入から舞曲へ入り、最後は加速する。実在の曲は使わない。
"""
from __future__ import annotations

from ..core.composer import RhythmMotif, ScaleRules
from ..core.model import ChordSpec, GmVoice
from ..core.pitch import CHORD_QUALITIES
from ..framework.context import Generator, MeasureCtx
from ..framework.gens import BassLine, Groove, hits
from ..framework.genre import Genre, Harmony, Kit, Part, Section
from ..framework.plan import Meter
from ..framework.registry import register_genre
from ._ornament import Heterophony, OrnamentedLead, WithTempo, inst as _inst

C = ChordSpec

METER = Meter(8, 4, (2, 4))
TEMPO = {"intro": (0.8, 0.8), "a": (1.0, 1.0), "b": (1.0, 1.0), "coda": (1.15, 1.3)}
GROOVES = {
    "main": hits("kick", (0,), 46) + hits("snare", (4,), 42) + hits("tamb", (2, 6), 22, 0.8),
    "intro": (),
}
LEAD_MOTIFS = {
    "doina": (RhythmMotif(rows=(0,)), RhythmMotif(rows=(0, 4)), RhythmMotif(rows=(0, 3))),
    "verse": (RhythmMotif(rows=(0, 2, 3, 4, 6)), RhythmMotif(rows=(0, 1, 2, 3, 4, 5, 6, 7)), RhythmMotif(rows=(0, 2, 4, 6))),
}
PROGRESSIONS = (
    ("i-V-i-V", (C(0, "min", label="i"), C(7, "maj", label="V"), C(0, "min", label="i"), C(7, "maj", label="V"))),
    ("i-iv-V-i", (C(0, "min", label="i"), C(5, "min", label="iv"), C(7, "maj", label="V"), C(0, "min", label="i"))),
    ("i-bII-V-i", (C(0, "min", label="i"), C(1, "maj", label="bII"), C(7, "maj", label="V"), C(0, "min", label="i"))),
)


class Pah(Generator):
    """アコーディオンの「パッ」（拍2）。裏拍に軽い刻みも足す。"""

    def measure(self, m: MeasureCtx) -> None:
        if m.plan.kind == "intro":
            if m.is_first:
                m.note(0, "bayan", m.m.chord.harmony, vel=m.scale_vol(26), dur=None)
            return
        shape = CHORD_QUALITIES[m.m.quality]
        m.note(4, "bayan", m.m.chord.harmony, vel=m.scale_vol(36), chord=shape, dur=3)
        for step in (2, 6):
            if m.rng.random() < 0.5:
                m.note(step, "bayan", m.m.chord.harmony, vel=m.scale_vol(22), chord=shape, dur=1)


def _sec(parts, *, prog=0, intensity=0.8, measures=8, groove="main", motifs="verse") -> Section:
    return Section(prog=prog, measures=measures, intensity=intensity, parts=frozenset(parts), groove=groove,
                   motifs=motifs, meter=METER)


@register_genre
class KlezmerGenre(Genre):
    id = "klezmer"
    category = "genre"
    display_name = "Klezmer"
    description = "クレズマー風。2/4 のオン・パッ、フリギア・ドミナントのクラリネット（すすり泣き）、ドイナ風の導入と加速するコーダ"
    description_en = "Klezmer style: 2/4 oom-pah, freygish clarinet with sobs, a doina-like intro and an accelerating coda"
    title = "Klezmer Dance"
    tempo_choices = (130, 136, 142, 148, 154)

    instruments = {
        "kick": _inst("perc_stomp", GmVoice(drum_note=35)),
        "snare": _inst("drum_pop_snare", GmVoice(drum_note=38)),
        "tamb": _inst("perc_tambourine", GmVoice(drum_note=54)),
        "tuba": _inst("march_tuba_bass", GmVoice(program=58)),
        "bayan": _inst("ru_bayan", GmVoice(program=21), name="Accordion"),
        "clar": _inst("klez_clarinet", GmVoice(program=71), volume=46),
        "violin": _inst("orch_violin", GmVoice(program=40), name="Fiddle", volume=34),
    }
    harmony = Harmony(keys=(2, 9, 7, 4), mode="phrygian_dominant", mode_by_quality={"min": "ukrainian_dorian"},
                      progressions=PROGRESSIONS, n_progressions=2)
    _band = {"drums", "bass", "pah", "lead"}
    sections = {
        "intro": _sec({"lead", "pah"}, intensity=0.5, measures=4, motifs="doina"),
        "a": _sec(_band, intensity=0.8),
        "b": _sec(_band, prog=1, intensity=0.9),
        "coda": _sec(_band, intensity=1.0),
    }
    form = ("intro", "a", "b", "a", "b", "coda")
    parts = (
        Part("drums", Groove(GROOVES), pan=128,
             kit=Kit(groups=(("kick/snare", ("kick", "snare")), ("tambourine", ("tamb",))),
                     priority={"snare": 3, "kick": 2}, single_priority={"kick": 3, "snare": 3, "tamb": 1},
                     group_pan={"tambourine": 168})),
        Part("bass", BassLine("tuba", kind="rootfifth", vol=52), pan=128),
        Part("pah", Pah(), pan=84),
        Part("lead", WithTempo(OrnamentedLead("clar", ScaleRules(leap_probability=0.15, leap_semitones=(3, 4, 5)),
                                              LEAD_MOTIFS, vol=46, gate=0.9, vibrato=0x35, scoop=0.35, grace=0.35, roll=0.2),
                               lambda sp: TEMPO[sp.name]), pan=172),
        Part("violin", Heterophony("violin", delay=1, drop=0.3, shift=0, vol_ratio=0.7, lo=12, hi=35, min_dur=1),
             follow="lead", pan=100, min_channels=6),
    )
    mod_channels = {4: 1, 6: 2}
