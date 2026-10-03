"""techno（旧 genres/techno.py の宣言を機械変換したもの。DESIGN.md §6）。"""
from __future__ import annotations

from ..core.model import ChordSpec, GmVoice
from ..core.synth_presets import PRESETS
from ..framework.gens import BassLine, Groove, hits
from ..framework.genre import Genre, Harmony, Instrument, Kit, Part, Section
from ..framework.context import Generator, MeasureCtx
from ..framework.registry import register_genre

C = ChordSpec


def _inst(key: str, gm: GmVoice, **changes) -> Instrument:
    patch = PRESETS[key]
    if changes:
        import dataclasses
        patch = dataclasses.replace(patch, **changes)
    return Instrument(patch=patch, gm=gm)

GROOVES = {
    "main": hits("kick", (0, 4, 8, 12), 60) + hits("ohat", (2, 6, 10, 14), 30) + hits("clap", (4, 12), 40),
    "hats": hits("kick", (0, 4, 8, 12), 60) + hits("hat", (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15), 22, 0.7) + hits("ohat", (2, 6, 10, 14), 28),
    "kick": hits("kick", (0, 4, 8, 12), 58),
}
PROGRESSIONS = (
    ("i7", (C(0, "m7", label="i7"),)),
    ("i7-bVII", (C(0, "m7", label="i7"), C(10, "maj", label="bVII"))),
)


BASE_SEQ = (0, 3, 6, 10, 11, 14)               # シーケンスの初期の発音位置（16分）


class Sequence(Generator):
    """シーケンス: 区間（pattern）ごとに16分の発音位置を1つずつ入れ替える（和音はほぼ固定。旧 extra_measure）。
    旧版の pattern.index（作成順の番号）は、区間の作成順の番号を SongPlan.sections から引く。"""

    def __init__(self, inst: str) -> None:
        self.inst = inst

    def measure(self, m: MeasureCtx) -> None:
        index = list(m.song.sections).index(m.plan.name)
        rows = list(BASE_SEQ)
        shift = (index * 4 + m.m.index // 4) % 16
        rows[shift % len(rows)] = (rows[shift % len(rows)] + 1 + shift) % 16
        tones = sorted({t for t in m.m.chord.chord_tones if 19 <= t <= 31}) or [m.m.chord.harmony + 12]
        for i, step in enumerate(sorted(set(rows))):
            if step < m.m.steps:
                m.note(step, self.inst, tones[(i + m.m.index) % len(tones)], vel=38 if step % 4 == 0 else 30)


@register_genre
class TechnoGenre(Genre):
    id = "techno"
    display_name = "Minimal Techno"
    description = "テクノ。繰り返しの中で少しずつ変わるシーケンスと4つ打ち"
    description_en = "Minimal techno: a hypnotic four-on-the-floor with slowly mutating sequences"
    title = "Minimal Techno"
    tempo_choices = (124, 126, 128, 130, 132)

    instruments = {
        "kick": _inst("drum_909_kick", GmVoice(drum_note=36)),
        "hat": _inst("drum_909_hat", GmVoice(drum_note=42)),
        "ohat": _inst("drum_909_open_hat", GmVoice(drum_note=46)),
        "clap": _inst("fb_clap", GmVoice(drum_note=39)),
        "bass": _inst("bass_synth_square", GmVoice(program=39)),
        "seq": _inst("syn_stab", GmVoice(program=62)),
    }
    harmony = Harmony(keys=(9, 2), mode="aeolian", progressions=PROGRESSIONS, n_progressions=1)
    sections = {
        "k1": Section(intensity=0.6, parts=frozenset({"drums"}), groove="kick"),
        "k2": Section(intensity=0.7, parts=frozenset({"bass", "drums"}), groove="kick"),
        "h1": Section(intensity=0.8, parts=frozenset({"bass", "drums", "comp"}), groove="hats"),
        "f1": Section(intensity=1.0, parts=frozenset({"bass", "drums", "comp"})),
        "f2": Section(intensity=1.0, parts=frozenset({"bass", "drums", "comp"})),
        "b1": Section(intensity=0.6, parts=frozenset({"bass", "comp"})),
        "f3": Section(intensity=1.0, parts=frozenset({"bass", "drums", "comp"})),
        "o1": Section(intensity=0.6, parts=frozenset({"drums"}), groove="hats"),
    }
    form = ("k1", "k2", "h1", "f1", "f2", "h1", "b1", "f3", "f2", "f3", "o1", "k1")
    parts = (
        Part("drums", Groove(GROOVES), pan=128,
             kit=Kit(groups=(("kick", ("kick",)), ("hats/clap", ("hat", "ohat", "clap"))),
                     priority={"clap": 3, "ohat": 2})),
        Part("bass", BassLine("bass", kind="offbeat", vol=48), pan=128),
        Part("comp", Sequence("seq"), pan=128),
    )
    mod_channels = {4: 1}
