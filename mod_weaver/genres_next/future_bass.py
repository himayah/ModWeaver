"""future-bass（旧 genres/future_bass.py の移植。FRAMEWORK_REDESIGN.md §15.4 のグループC）。

1小節 = 16 step = 4/4。キック（とクラップ）をトリガにしたサイドチェイン・ダッキング（``Genre.mix``）と、
サンプル・スライサー（vocal chop。``Offset(i / N_SLICES)``）が特徴。Eb メジャーの I-V-vi-IV を4小節で回す。
"""
from __future__ import annotations

from ..core.harmony import Registers
from ..core.model import ChordSpec, GmVoice
from ..core.synth_presets import PRESETS
from ..framework.context import Generator, MeasureCtx
from ..framework.genre import Genre, Harmony, Instrument, Kit, Part, Section, Sidechain
from ..framework.registry import register_genre
from ..framework.score import Offset

KEY_PC = 3                                    # Eb
BASS_REG = (0, 11)                            # sub（shift=-12 → t=12..23）
CHORD_REG = (12, 23)                          # supersaw の根音（chord.harmony）
UNUSED_MELODY_REG = (24, 35)                  # Registers の必須フィールド（future-bass では未使用）

# (root, quality) — Eb（KEY_PC）基準の半音オフセット。I - V - vi - IV
PROGRESSION = (ChordSpec(0, "maj"), ChordSpec(7, "maj"), ChordSpec(9, "min"), ChordSpec(5, "maj"))

FOUR_ON_FLOOR = (0, 4, 8, 12)
CLAP_BACKBEAT = (4, 12)
CLAP_OFFBEAT_8TH = (2, 6, 10, 14)          # buildup のハイハット代用
VOCAL_CHOP_ROWS = (0, 2, 4, 6, 8, 10, 12, 14)
N_SLICES = 6


class FutureKick(Generator):
    """buildup は kick 4つ打ち＋clap を8分オフビートへ（ハイハット代わり）、drop は kick 4つ打ち＋clap のバックビート。"""

    def measure(self, m: MeasureCtx) -> None:
        if m.plan.kind == "buildup":
            for step in FOUR_ON_FLOOR:
                m.note(step, "kick", vel=56)
            for step in CLAP_OFFBEAT_8TH:
                m.note(step, "clap", vel=32)
        else:
            for step in FOUR_ON_FLOOR:
                m.note(step, "kick", vel=58)
            for step in CLAP_BACKBEAT:
                m.note(step, "clap", vel=44)       # Kit の優先度でバックビートのキックに勝つ


class SustainedChord(Generator):
    """区間の各小節の頭に持続音を1つ。drop は ``intensity × 56``、breakdown・outro は kick 抜きで柔らかく ``intensity × 48``。"""

    def __init__(self, inst: str, pitch_of) -> None:
        self.inst = inst
        self.pitch_of = pitch_of

    def measure(self, m: MeasureCtx) -> None:
        base = 56 if m.plan.kind == "drop" else 48
        m.note(0, self.inst, self.pitch_of(m.m.chord), vel=max(1, round(base * m.plan.intensity)))


class VocalChop(Generator):
    """vox のみ。長尺サンプルを N_SLICES 個のシラブルに分割して叩く（``Offset``）。音量はサンプル既定音量。"""

    def measure(self, m: MeasureCtx) -> None:
        for step in VOCAL_CHOP_ROWS:
            if m.rng.random() < 0.7:
                i = m.rng.randrange(N_SLICES)
                m.note(step, "vox", arts=(Offset(i / N_SLICES),))


def _inst(key: str, gm: GmVoice) -> Instrument:
    return Instrument(patch=PRESETS[key], gm=gm)


@register_genre
class FutureBassGenre(Genre):
    id = "future-bass"
    category = "style"
    display_name = "Future Bass"
    description = "フューチャーベース。キック連動サイドチェイン、ヴォーカルチョップ、Eb I-V-vi-IV"
    description_en = "Future bass: kick-triggered sidechain, vocal chops, Eb I-V-vi-IV"
    title = "Future Bass"
    tempo_choices = (148, 150, 152, 155, 160)

    instruments = {
        "kick": _inst("fb_kick", GmVoice(drum_note=36)),
        "sub": _inst("fb_sub", GmVoice(program=38)),
        "saw": _inst("fb_supersaw", GmVoice(program=81)),
        "vox": _inst("fb_vocal_chop", GmVoice(program=53)),
        "clap": _inst("fb_clap", GmVoice(drum_note=39)),
    }
    harmony = Harmony(keys=(KEY_PC,), mode="ionian", progressions=(("I-V-vi-IV", PROGRESSION),), n_progressions=1,
                       fixed=True, registers=Registers(bass=BASS_REG, harmony=CHORD_REG, melody=UNUSED_MELODY_REG))
    sections = {
        "intro_chop": Section(intensity=0.3, parts=frozenset({"vox"})),
        "buildup": Section(intensity=0.5, parts=frozenset({"kick"})),
        "drop": Section(intensity=1.0, parts=frozenset({"kick", "sub", "chord"})),
        "breakdown": Section(intensity=0.4, parts=frozenset({"sub", "chord"})),
        "outro": Section(intensity=0.25, parts=frozenset({"sub", "chord"})),
    }
    form = ("intro_chop", "intro_chop", "buildup", "drop", "drop", "breakdown", "drop", "drop", "outro")
    parts = (
        Part("kick", FutureKick(), pan=128,
             kit=Kit(groups=(("kick", ("kick", "clap")),), priority={"clap": 2, "kick": 1})),
        Part("sub", SustainedChord("sub", lambda c: c.bass), pan=128),
        Part("chord", SustainedChord("saw", lambda c: c.harmony), pan=144),
        Part("vox", VocalChop(), pan=112),
    )
    # clap が kick を置換するバックビートでも4拍ともポンピングを保つため、kick と clap の両方をトリガにする
    mix = (
        Sidechain(triggers=("kick", "clap"), targets=("sub",), ratio=0.25, release_steps=3),
        Sidechain(triggers=("kick", "clap"), targets=("chord",), ratio=0.35, release_steps=4),
    )
    mod_channels = {4: 1}
