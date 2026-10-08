"""gospel-shout（ゴスペルのシャウト。NEW_GENRES_DESIGN.md §14.2）。

150〜172 BPM の2:1 にハネるシャッフル、シャウトの和声進行（I–I7–IV–#iv°7–I/V–V7–I…）、ハンドクラップ（2・4拍）、
オルガンのグリッサンド、聖歌隊、最後のヴァンプで倍速（開始 BPM の1.2〜1.25倍）。
"""
from __future__ import annotations

from ..core.composer import RhythmMotif, ScaleRules
from ..core.model import ChordSpec, GmVoice
from ..framework.gens import BassLine, Choir, Comp, Groove, Layer, Sing, hits
from ..framework.genre import Genre, Harmony, Kit, Part, Section, Voice
from ..framework.plan import Meter, Swing
from ..framework.registry import register_genre
from ._ornament import OrnamentedLead, WithTempo, inst as _inst

C = ChordSpec

METER = Meter(8, 2)                           # 8分の格子。Swing(16, 8) で 2:1 のシャッフル
SWING = Swing(16, 8)
GROOVES = {
    "main": hits("kick", (0, 4), 52) + hits("snare", (2, 6), 48) + hits("clap", (2, 6), 40)
            + hits("tamb", (1, 3, 5, 7), 20, 0.8),
    "vamp": hits("kick", (0, 2, 4, 6), 54) + hits("snare", (2, 6), 52) + hits("clap", (1, 2, 3, 5, 6, 7), 38)
            + hits("tamb", tuple(range(8)), 24),
}
LEAD_MOTIFS = {
    "verse": (RhythmMotif(rows=(0, 2, 3, 4, 6)), RhythmMotif(rows=(0, 1, 2, 4, 6)), RhythmMotif(rows=(0, 3, 4, 6))),
    "shout": (RhythmMotif(rows=(0, 1, 2, 3, 4, 5, 6, 7)), RhythmMotif(rows=(0, 2, 3, 4, 5, 6)), RhythmMotif(rows=(0, 1, 2, 4, 5, 6))),
}
SHOUT = (C(0, "maj", label="I"), C(0, "dom7", label="I7"), C(5, "maj", label="IV"), C(6, "dim7", label="#iv"),
         C(0, "maj", bass=7, label="I/V"), C(7, "dom7", label="V7"), C(0, "maj", label="I"), C(7, "dom7", label="V7"))
PROGRESSIONS = (
    ("shout", SHOUT),
    ("I-IV-I-V7", (C(0, "maj", label="I"), C(5, "maj", label="IV"), C(0, "maj", label="I"), C(7, "dom7", label="V7"))),
    ("I-vi-IV-V7", (C(0, "maj", label="I"), C(9, "min", label="vi"), C(5, "maj", label="IV"), C(7, "dom7", label="V7"))),
)
TEMPO = {"vamp": (1.2, 1.25), "outro": (1.25, 1.0)}


def _sec(parts, *, prog=0, intensity=0.8, measures=8, groove="main", motifs="verse") -> Section:
    return Section(prog=prog, measures=measures, intensity=intensity, parts=frozenset(parts), groove=groove,
                   motifs=motifs, swing=SWING, meter=METER)


@register_genre
class GospelShoutGenre(Genre):
    id = "gospel-shout"
    category = "style"
    display_name = "Gospel Shout"
    description = "ゴスペルのシャウト。ハネるシャッフル、シャウトの和声、ハンドクラップ、オルガンのグリッサンド、倍速のヴァンプ（--voice でリードを歌い、聖歌隊が重なる）"
    description_en = "Gospel shout: swung shuffle, shout chord changes, handclaps, organ glissandi and a double-time vamp (a sung lead and choir with --voice)"
    title = "Gospel Shout"
    tempo_choices = (150, 156, 162, 168, 172)

    instruments = {
        "kick": _inst("drum_pop_kick", GmVoice(drum_note=36)),
        "snare": _inst("drum_pop_snare", GmVoice(drum_note=38)),
        "clap": _inst("fb_clap", GmVoice(drum_note=39)),
        "tamb": _inst("perc_tambourine", GmVoice(drum_note=54)),
        "bass": _inst("bass_finger", GmVoice(program=33)),
        "piano": _inst("keys_piano", GmVoice(program=0), volume=38),
        "organ": _inst("keys_organ", GmVoice(program=16), volume=40),
        "choir": _inst("vox_choir", GmVoice(program=52), volume=30),
        "voice": Voice(GmVoice(program=54), timbre="female", volume=46),     # --voice で歌う（旋律は lead と同じ）
        "vchoir": Voice(GmVoice(program=52), timbre="choir", volume=40),     # --voice で「あ」を歌う（和音の各声）
    }
    harmony = Harmony(keys=(0, 5, 7, 2), mode="ionian", progressions=PROGRESSIONS, n_progressions=2)
    _band = {"drums", "bass", "comp", "lead"}
    sections = {
        "intro": _sec({"drums", "comp", "bass"}, intensity=0.6, measures=4),
        "verse": _sec(_band | {"vocal"}, intensity=0.75),
        "chorus": _sec(_band | {"choir", "vchoir", "vocal"}, prog=1, intensity=0.95, motifs="shout"),
        "vamp": _sec(_band | {"choir", "vchoir", "vocal"}, prog=0, intensity=1.0, groove="vamp", motifs="shout"),
        "outro": _sec({"drums", "comp", "lead", "bass"}, intensity=0.7, measures=4, groove="vamp"),
    }
    form = ("intro", "verse", "chorus", "verse", "chorus", "vamp", "outro")
    parts = (
        Part("drums", WithTempo(Groove(GROOVES), lambda sp: TEMPO.get(sp.name, (1.0, 1.0))), pan=128,
             kit=Kit(groups=(("kick/snare", ("kick", "snare")), ("clap/tamb", ("clap", "tamb"))),
                     priority={"snare": 3, "kick": 2, "clap": 2}, single_priority={"kick": 3, "snare": 3, "clap": 2, "tamb": 1},
                     group_pan={"clap/tamb": 160})),
        Part("bass", BassLine("bass", kind="walking", vol=52), pan=128),
        Part("comp", Comp("piano", kind="charleston", vol=38), pan=84),
        Part("lead", OrnamentedLead("organ", ScaleRules(leap_probability=0.15, leap_semitones=(3, 4, 5)), LEAD_MOTIFS,
                                    vol=44, gate=0.9, vibrato=0x35, scoop=0.5, grace=0.25), pan=172),
        Part("choir", Layer("choir", vol=28, chordal=True), follow="comp", pan=128, min_channels=6),
        Part("vocal", Sing("voice", min_dur=2, vel_ratio=1.9), pan=128, depends=("lead",), min_channels=6,
             requires=frozenset({"voice"}), ducks=("lead", "comp", "choir", "vchoir"), duck_ratio=0.25,
             duck_ratios=(("lead", 0.1), ("vchoir", 0.3))),
        Part("vchoir", Choir("vchoir", vol=50), poly=3, pan=128, min_channels=10, requires=frozenset({"voice"}),
             ducks=("choir", "comp", "lead"), duck_ratio=0.4, duck_ratios=(("lead", 0.5),)),
    )
    mod_channels = {4: 1, 6: 2, 8: 1}
