"""gagaku（雅楽風。NEW_GENRES_DESIGN.md §4）。

笙風の持続和音（合竹）、篳篥風の長い旋律（塩梅＝下からのしゃくり）、龍笛風の異種同音、鞨鼓・太鼓・鉦鼓。
序・破・急でテンポが段階的に速くなる。呂（major_pent）か律（ritsu）の音階を seed で選ぶ。雅楽そのものの再現ではない。
"""
from __future__ import annotations

from ..core.composer import RhythmMotif, ScaleRules
from ..core.model import ChordSpec, GmVoice
from ..framework.context import Generator, MeasureCtx
from ..framework.gens import Arp, Choir, Groove, Sing, hits
from ..framework.genre import Genre, Harmony, Kit, Part, Section, Voice
from ..framework.registry import register_genre
from ._ornament import Heterophony, OrnamentedLead, WithTempo, inst as _inst

C = ChordSpec

TEMPO = {"jo": (1.0, 1.0), "ha": (1.0, 1.2), "kyu": (1.25, 1.5), "outro": (1.5, 0.75)}
SHO_SHAPES = ((0, 5, 7, 12), (0, 7, 12, 14), (0, 2, 7, 12))        # 合竹（根音からの半音）。4小節ごとに替える
GROOVES = {
    "jo": hits("shoko", (0,), 30),
    "ha": hits("taiko", (0,), 54) + hits("shoko", (8,), 30) + hits("kakko", (4, 12), 24, 0.7),
    "kyu": hits("taiko", (0, 8), 56) + hits("kakko", tuple(range(0, 16, 2)), 22) + hits("shoko", (4, 12), 28),
}
LEAD_MOTIFS = {
    "jo": (RhythmMotif(rows=(0,)), RhythmMotif(rows=(0, 8))),
    "ha": (RhythmMotif(rows=(0, 8)), RhythmMotif(rows=(0, 6, 12)), RhythmMotif(rows=(0, 4, 8))),
    "kyu": (RhythmMotif(rows=(0, 4, 8, 12)), RhythmMotif(rows=(0, 4, 6, 8, 12))),
}
PROGRESSIONS = (
    ("Ryo (major pentatonic)", (C(0, "sus4", label="ryo"),)),
    ("Ritsu", (C(0, "sus2", label="ritsu"),)),
)


class Sho(Generator):
    """合竹を1つの和音として区間の頭と4小節ごとに鳴らし直す（持続音。和音を焼けない予算では声部に開く）。"""

    inst = "sho"

    def measure(self, m: MeasureCtx) -> None:
        if m.m.index % 4 == 0:
            shape = SHO_SHAPES[(m.m.index // 4) % len(SHO_SHAPES)]
            m.note(0, "sho", m.m.chord.harmony, vel=m.scale_vol(30), chord=shape, dur=None)


def _sec(parts, *, intensity, measures, motifs, groove) -> Section:
    return Section(measures=measures, intensity=intensity, parts=frozenset(parts), motifs=motifs, groove=groove)


@register_genre
class GagakuGenre(Genre):
    id = "gagaku"
    category = "genre"
    display_name = "Gagaku (Court Music Style)"
    description = "雅楽風。笙・篳篥・龍笛風の音色、塩梅（しゃくり）、序破急のテンポ変化（雅楽そのものの再現ではない。--voice で旋律を歌い、合唱を加えられる）"
    description_en = "Gagaku-style court music: sho-like sustained chords, hichiriki-like melody with scoops, jo-ha-kyu tempo (not a faithful reproduction; a sung lead and choir with --voice)"
    title = "Gagaku Suite"
    tempo_choices = (46, 50, 54, 58)

    instruments = {
        "taiko": _inst("perc_taiko", GmVoice(drum_note=41)),
        "kakko": _inst("jp_kakko", GmVoice(drum_note=60)),
        "shoko": _inst("jp_shoko", GmVoice(drum_note=81)),
        "sho": _inst("jp_sho", GmVoice(program=109), volume=40),
        "hichiriki": _inst("jp_hichiriki", GmVoice(program=68), volume=44),
        "ryuteki": _inst("jp_ryuteki", GmVoice(program=73), volume=34),
        "biwa": _inst("jp_biwa", GmVoice(program=106)),
        "voice": Voice(GmVoice(program=54), timbre="female", volume=46),     # --voice で歌う（旋律は hichiriki と同じ）
        "vchoir": Voice(GmVoice(program=52), timbre="choir", volume=36),     # --voice で笙の合竹に重ねて「あ」を歌う
    }
    harmony = Harmony(keys=(2, 7, 9, 4), mode="major_pent", mode_by_quality={"sus4": "major_pent", "sus2": "ritsu"},
                      progressions=PROGRESSIONS, n_progressions=1)
    sections = {
        "jo": _sec({"sho", "drums"}, intensity=0.5, measures=8, motifs="jo", groove="jo"),
        "ha": _sec({"sho", "drums", "hichiriki", "biwa", "vchoir", "vocal"}, intensity=0.75, measures=12, motifs="ha", groove="ha"),
        "kyu": _sec({"sho", "drums", "hichiriki", "biwa", "vchoir", "vocal"}, intensity=1.0, measures=12, motifs="kyu", groove="kyu"),
        "outro": _sec({"sho", "drums", "hichiriki", "vocal"}, intensity=0.4, measures=4, motifs="jo", groove="jo"),
    }
    form = ("jo", "ha", "kyu", "outro")
    parts = (
        Part("drums", WithTempo(Groove(GROOVES), lambda sp: TEMPO[sp.name]), pan=128,
             kit=Kit(groups=(("taiko/kakko", ("taiko", "kakko")), ("shoko", ("shoko",))),
                     priority={"taiko": 3, "kakko": 1}, single_priority={"taiko": 3, "kakko": 1, "shoko": 2},
                     group_pan={"shoko": 168})),
        Part("sho", Sho(), pan=128),
        Part("hichiriki", OrnamentedLead("hichiriki", ScaleRules(leap_probability=0.08, leap_semitones=(5, 7)),
                                         LEAD_MOTIFS, vol=44, gate=1.0, vibrato=0x22, scoop=0.6, scoop_semitones=2.0),
             pan=150),
        Part("ryuteki", Heterophony("ryuteki", delay=2, drop=0.35, shift=0, vol_ratio=0.75, lo=12, hi=35, min_dur=2),
             follow="hichiriki", pan=96, min_channels=6),
        Part("biwa", Arp("biwa", (12, 28), (0, 8), vol=34), pan=70, min_channels=6),
        Part("vocal", Sing("voice", source="hichiriki", vel_ratio=1.4), pan=128, depends=("hichiriki",), min_channels=6,
             requires=frozenset({"voice"}), ducks=("hichiriki", "ryuteki", "sho", "biwa", "vchoir"), duck_ratio=0.3,
             duck_ratios=(("hichiriki", 0.1), ("ryuteki", 0.2))),
        Part("vchoir", Choir("vchoir", vol=40), poly=3, pan=128, min_channels=10, requires=frozenset({"voice"}),
             ducks=("sho",), duck_ratio=0.5),
    )
    mod_channels = {4: 1, 6: 2}
