"""rokyoku（浪曲風。NEW_GENRES_DESIGN.md §7）。

三味線を中心にした疎な編成。「節（旋律あり）」と「啖呵（旋律が止まり、三味線が一定の刻みだけを弾く間）」を交互に置き、
緩急の大きいテンポ（区間ごとの倍率）で語り物の呼吸を作る。語り・歌は含まない。
"""
from __future__ import annotations

from ..core.composer import RhythmMotif, ScaleRules
from ..core.model import ChordSpec, GmVoice
from ..core.pitch import CHORD_QUALITIES
from ..framework.context import Generator, MeasureCtx
from ..framework.gens._common import arp_tones
from ..framework.genre import Genre, Harmony, Kit, Part, Section
from ..framework.registry import register_genre
from ._ornament import Drone, OrnamentedLead, WithTempo, inst as _inst

C = ChordSpec

TEMPO = {                                    # 区間名 -> 開始 BPM に対する倍率（開始, 終了）
    "maku": (1.0, 1.0), "fushi1": (1.0, 1.0), "tanka1": (0.75, 0.75), "fushi2": (1.0, 0.95),
    "tanka2": (0.75, 0.7), "fushi3": (1.05, 1.2), "outro": (1.2, 0.8),
}
LEAD_MOTIFS = {
    "fushi": (RhythmMotif(rows=(0, 6, 8)), RhythmMotif(rows=(0, 4, 8, 12)), RhythmMotif(rows=(0, 8, 12))),
    "climax": (RhythmMotif(rows=(0, 4, 6, 8, 12)), RhythmMotif(rows=(0, 2, 4, 8, 10, 12)), RhythmMotif(rows=(0, 4, 8, 10))),
}
PROGRESSIONS = (
    ("I-bII-I-iv", (C(0, "sus4", label="I"), C(1, "maj", label="bII"), C(0, "sus4", label="I"), C(5, "min", label="iv"))),
    ("I-iv-bII-I", (C(0, "sus4", label="I"), C(5, "min", label="iv"), C(1, "maj", label="bII"), C(0, "sus4", label="I"))),
)


class RokyokuShamisen(Generator):
    """区間の種類（kind）で弾き方を変える: 節＝和音の撥と合間の単音、啖呵＝一定の8分の刻み、幕＝上行の分散、
    終わり＝和音の一撃。節の最後の小節には下行の合いの手を添える。"""

    def measure(self, m: MeasureCtx) -> None:
        kind = m.plan.kind
        chord = m.m.chord
        shape = CHORD_QUALITIES[m.m.quality]
        if kind == "tanka":
            for step in range(0, m.m.steps, 2):
                m.note(step, "shamisen", chord.harmony, vel=m.scale_vol(34 if step % 8 == 0 else 24))
        elif kind == "maku":
            for i, step in enumerate((0, 4, 8, 12)):
                tones = arp_tones(chord, (12, 28))
                m.note(step, "shamisen", tones[i % len(tones)], vel=m.scale_vol(36))
        elif kind == "outro":
            if m.is_last:
                m.note(0, "shamisen", chord.harmony, vel=m.scale_vol(60), chord=shape, strum_ms=16.0)
            elif m.m.index % 2 == 0:
                m.note(0, "shamisen", chord.harmony, vel=m.scale_vol(44), chord=shape, strum_ms=14.0)
        else:                                                    # fushi
            m.note(0, "shamisen", chord.harmony, vel=m.scale_vol(42), chord=shape, strum_ms=14.0)
            m.note(8, "shamisen", chord.harmony, vel=m.scale_vol(34), chord=shape, strum_ms=14.0)
            for step in (4, 12):
                m.note(step, "shamisen", chord.harmony, vel=m.scale_vol(26))
            if m.is_last:
                tones = sorted(chord.scale_tones)
                top = max((i for i, t in enumerate(tones) if t <= 31), default=len(tones) - 1)
                for k, step in enumerate((14, 15)):
                    m.note(step, "shamisen", tones[max(0, top - 2 - k)], vel=m.scale_vol(38))


class Taiko(Generator):
    """山場（fushi3）の2小節ごとの頭と、終わり（outro）の最後の一打だけ打つ。"""

    def measure(self, m: MeasureCtx) -> None:
        if m.plan.kind == "outro":
            if m.is_last:
                m.note(0, "taiko", vel=64)
        elif m.m.index % 2 == 0:
            m.note(0, "taiko", vel=m.scale_vol(56))


def _sec(parts, *, prog=0, intensity=0.8, measures=8, motifs="fushi", kind="") -> Section:
    return Section(prog=prog, measures=measures, intensity=intensity, parts=frozenset(parts), motifs=motifs, kind=kind)


@register_genre
class RokyokuGenre(Genre):
    id = "rokyoku"
    category = "style"
    display_name = "Rokyoku Style"
    description = "浪曲風。三味線を中心にした疎な編成、節と啖呵（間）の交替、緩急の大きいテンポ（語り・歌は含まない）"
    description_en = "Rokyoku style: sparse shamisen-led ensemble, melodic fushi alternating with spoken-style tanka gaps, wide tempo swings (no voice)"
    title = "Rokyoku Tale"
    tempo_choices = (84, 88, 92, 96, 100)

    instruments = {
        "shamisen": _inst("jp_shamisen", GmVoice(program=106)),
        "flute": _inst("jp_shakuhachi", GmVoice(program=77), volume=42),
        "taiko": _inst("perc_taiko", GmVoice(drum_note=41)),
        "drone": _inst("bass_deep", GmVoice(program=33), volume=28),
    }
    harmony = Harmony(keys=(2, 9, 4, 7), mode="miyakobushi", progressions=PROGRESSIONS, n_progressions=2)
    sections = {
        "maku": _sec({"shamisen"}, intensity=0.5, measures=4, kind="maku"),
        "fushi1": _sec({"shamisen", "lead", "drone"}, intensity=0.7, kind="fushi"),
        "tanka1": _sec({"shamisen", "drone"}, intensity=0.5, measures=4, kind="tanka"),
        "fushi2": _sec({"shamisen", "lead", "drone"}, prog=1, intensity=0.8, kind="fushi"),
        "tanka2": _sec({"shamisen", "drone"}, intensity=0.6, measures=4, kind="tanka"),
        "fushi3": _sec({"shamisen", "lead", "drone", "taiko"}, prog=1, intensity=1.0, motifs="climax", kind="fushi"),
        "outro": _sec({"shamisen", "lead", "taiko"}, intensity=0.6, measures=4, kind="outro"),
    }
    form = ("maku", "fushi1", "tanka1", "fushi2", "tanka2", "fushi3", "outro")
    parts = (
        Part("shamisen", WithTempo(RokyokuShamisen(), lambda sp: TEMPO[sp.name]), pan=110),
        Part("lead", OrnamentedLead("flute", ScaleRules(leap_probability=0.08, leap_semitones=(4, 5, 7)), LEAD_MOTIFS,
                                    vol=44, gate=1.0, vibrato=0x33, scoop=0.45, kobushi=0.3), pan=160),
        Part("taiko", Taiko(), pan=128, min_channels=6,
             kit=Kit(groups=(("taiko", ("taiko",)),), priority={"taiko": 1})),
        Part("drone", Drone("drone", 28), pan=128, min_channels=6),
    )
    mod_channels = {4: 2, 6: 1}
