"""baroque（バロック風。NEW_GENRES_DESIGN.md §14.6）。

深さは「進行（5度圏の下行）＋ゼクエンツ＋通奏低音」まで（フーガの模倣はしない）: 1小節ごとに5度下がる和声に、
動機を1音ずつ下げて繰り返す旋律（ゼクエンツ）、チェンバロの和音と8分の通奏低音、終止の装飾（トリル）、
強弱は区間ごとの段階（テラス・ダイナミクス）。
"""
from __future__ import annotations

from ..core.model import ChordSpec, GmVoice
from ..core.pitch import fold_into_range
from ..framework.context import Generator, MeasureCtx, SectionCtx
from ..framework.gens import Comp, Pad
from ..framework.genre import Genre, Harmony, Part, Section
from ..framework.registry import register_genre
from ..framework.score import Arpeggio
from ._ornament import Heterophony, inst as _inst

C = ChordSpec

# 5度圏の下行（i-iv-VII-III-VI-iiø-V-i）と、パッヘルベル風の変形（i-V-VI-III-iv-i-iv-V）
FIFTHS = (C(0, "min", label="i"), C(5, "min", label="iv"), C(10, "maj", label="VII"), C(3, "maj", label="III"),
          C(8, "maj", label="VI"), C(2, "dim", label="iio"), C(7, "dom7", label="V7"), C(0, "min", label="i"))
CANON = (C(0, "min", label="i"), C(7, "maj", label="V"), C(8, "maj", label="VI"), C(3, "maj", label="III"),
         C(5, "min", label="iv"), C(0, "min", label="i"), C(5, "min", label="iv"), C(7, "dom7", label="V7"))
PROGRESSIONS = (("circle of fifths", FIFTHS), ("canon-like", CANON))
# 動機: 8分音符8つの度数オフセット（小節ごとに開始度数を1つ下げて繰り返す）
PATTERNS = ((0, 2, 1, 3, 2, 4, 3, 5), (0, 1, 2, 0, 3, 2, 4, 3), (4, 3, 2, 1, 3, 2, 1, 0), (0, 4, 2, 4, 1, 3, 0, 2))


class SequenceLead(Generator):
    """ゼクエンツ: 区間で選んだ動機を、1小節ごとに音階上で1度ずつ下げて繰り返す。coda の最後の小節は主音の長い音にトリル。"""

    inst = "violin"

    def section(self, ctx: SectionCtx) -> None:
        reg = ctx.genre.harmony.registers.melody
        ctx.state["notes"] = ctx.plan.scale.notes_in(*reg)
        ctx.state["pattern"] = ctx.rng.choice(PATTERNS)
        n = len(ctx.state["notes"])
        ctx.state["start"] = min(n - 1, n // 2 + 2 + ctx.rng.randint(0, 2))
        super().section(ctx)

    def measure(self, m: MeasureCtx) -> None:
        notes = m.state["notes"]
        if m.plan.name == "coda" and m.is_last:
            tonic = fold_into_range(m.plan.tonic, 24, 35)
            m.note(0, "violin", tonic, vel=m.scale_vol(50), dur=m.m.steps, arts=(Arpeggio(0, 2, steps=m.m.steps),))
            return
        base = m.state["start"] - m.m.index
        for k, off in enumerate(m.state["pattern"]):
            step = k * 2
            if step >= m.m.steps:
                break
            idx = max(0, min(len(notes) - 1, base + off))
            m.note(step, "violin", notes[idx], vel=m.scale_vol(48 if k % 2 == 0 else 40), dur=2)


class Continuo(Generator):
    """通奏低音: 8分音符で根音・5度・オクターブを巡る。"""

    def measure(self, m: MeasureCtx) -> None:
        reg = m.genre.harmony.registers.bass
        root = m.m.chord.bass
        fifth = fold_into_range(root + 7, *reg)
        octave = fold_into_range(root + 12, reg[0], reg[1] + 12)
        cycle = (root, fifth, octave, fifth)
        for k in range(0, m.m.steps, 2):
            m.note(k, "cello", cycle[(k // 2) % 4], vel=m.scale_vol(50 if k % 8 == 0 else 40), dur=2)


def _sec(parts, *, prog=0, intensity=0.9, measures=8) -> Section:
    return Section(prog=prog, measures=measures, intensity=intensity, parts=frozenset(parts))


@register_genre
class BaroqueGenre(Genre):
    id = "baroque"
    category = "genre"
    display_name = "Baroque"
    description = "バロック風。5度圏の和声、ゼクエンツ、チェンバロと8分の通奏低音、終止のトリル、区間ごとの強弱の段階"
    description_en = "Baroque style: circle-of-fifths harmony, melodic sequences, harpsichord and walking continuo, cadential trill, terraced dynamics"
    title = "Baroque Sequence"
    tempo_choices = (100, 104, 108, 112, 116, 120)

    instruments = {
        "violin": _inst("orch_violin", GmVoice(program=40), name="BaroqueViolin", volume=44),
        "cello": _inst("swing_walk_bass", GmVoice(program=42), name="Continuo", volume=50),
        "harpsichord": _inst("baroque_harpsichord", GmVoice(program=6)),
        "flute": _inst("wind_flute", GmVoice(program=74), name="Recorder", volume=32),
        "organ": _inst("keys_organ", GmVoice(program=19), volume=26),
    }
    harmony = Harmony(keys=(2, 9, 4, 7), mode="aeolian", progressions=PROGRESSIONS, fixed=True)
    _band = {"lead", "comp", "bass"}
    sections = {
        "intro": _sec({"comp", "bass"}, intensity=0.9, measures=4),
        "a": _sec(_band, intensity=0.95),                      # フォルテ（tutti）
        "b": _sec(_band, prog=1, intensity=0.5),              # ピアノ（ソロ）
        "coda": _sec(_band | {"organ"}, prog=0, intensity=1.0),
    }
    form = ("intro", "a", "b", "a", "b", "coda")
    parts = (
        Part("lead", SequenceLead(), pan=172),
        Part("comp", Comp("harpsichord", kind="half", vol=40, strum_ms=18.0), pan=84),
        Part("bass", Continuo(), pan=128),
        Part("flute", Heterophony("flute", delay=4, drop=0.1, shift=0, vol_ratio=0.7, lo=12, hi=35, min_dur=1),
             follow="lead", pan=100, min_channels=6),
        Part("organ", Pad("organ", vol=26, chordal=False), pan=128, min_channels=8),
    )
    mod_channels = {4: 1, 6: 2, 8: 1}
