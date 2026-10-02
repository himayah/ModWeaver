"""ambient-drone（旧 genres/ambient_drone.py の宣言を機械変換したもの。FRAMEWORK_REDESIGN.md §15）。"""
# TODO(F6): 論理チャンネル ['drone', 'fifth', 'upper', 'swell'] を鳴らすパートが宣言に無い（上書きメソッドで鳴らす）
from __future__ import annotations

from ..core.model import ChordSpec, GmVoice
from ..core.synth_presets import PRESETS
from ..framework.genre import Genre, Harmony, Instrument, Kit, Part, Section
from ..framework.context import Generator, MeasureCtx
import math
from ..core.pitch import MODES, fold_into_range
from ..framework.registry import register_genre

C = ChordSpec


def _inst(key: str, gm: GmVoice, **changes) -> Instrument:
    patch = PRESETS[key]
    if changes:
        import dataclasses
        patch = dataclasses.replace(patch, **changes)
    return Instrument(patch=patch, gm=gm)

PROGRESSIONS = (
    ("i drone", (C(0, "min", label="i"),)),
)


UPPER_REGISTER = (24, 35)
SWELL_STEPS = (4, 8, 12)                       # 持続音の音量を書き換える step（1小節に3回）
# 区間 → 上の音の主音からの音階の段。None なら鳴らさない
DEGREE = {"d1": None, "d2": 2, "d3": 4, "d4": 6, "d5": 5, "d6": 3, "d7": 1, "d8": None}


def level(m: MeasureCtx, step: int) -> int:
    """4小節周期のうねり（0.75〜1.0 倍）をかけた持続音の音量。"""
    base = 20 + 36 * m.plan.intensity
    phase = (m.m.index * 16 + step) / 64.0
    return max(1, min(64, round(base * (0.875 - 0.125 * math.cos(2 * math.pi * phase)))))


class Drone(Generator):
    """長い持続音（ドローン・5度）。小節の頭で1回だけ鳴らし、音量のうねりは Automation で書く。"""

    def __init__(self, inst: str, factor: float = 1.0, root_register: tuple[int, int] = (0, 11),
                 interval: int = 0) -> None:
        self.inst = inst
        self.factor = factor
        self.register = root_register
        self.interval = interval

    def measure(self, m: MeasureCtx) -> None:
        if m.m.index == 0:
            tone = fold_into_range(m.plan.tonic + self.interval, *self.register)
            m.note(0, self.inst, tone, vel=round(level(m, 0) * self.factor))
        for step in SWELL_STEPS:
            m.automate(step, "volume", round(level(m, step) * self.factor))


class UpperTone(Generator):
    """上の音: 区間ごとに決まった音階の段を1音だけ長く伸ばす（DEGREE）。"""

    def __init__(self, inst: str) -> None:
        self.inst = inst

    def measure(self, m: MeasureCtx) -> None:
        degree = DEGREE[m.plan.kind]
        if degree is None:
            return
        if m.m.index == 0:
            steps = MODES[m.genre.harmony.mode]
            pc = (m.plan.tonic + steps[degree % len(steps)]) % 12
            m.note(0, self.inst, fold_into_range(pc, *UPPER_REGISTER), vel=round(level(m, 0) * 0.7))
        for step in SWELL_STEPS:
            m.automate(step, "volume", round(level(m, step) * 0.7))


class CymbalSwell(Generator):
    """3小節目に、強い区間だけシンバルのスウェル。"""

    def __init__(self, inst: str) -> None:
        self.inst = inst

    def measure(self, m: MeasureCtx) -> None:
        if m.m.index == 2 and m.plan.intensity >= 0.5:
            m.note(0, self.inst, vel=round(20 + 20 * m.plan.intensity))


@register_genre
class AmbientDroneGenre(Genre):
    id = "ambient-drone"
    category = "style"
    display_name = "Ambient Drone"
    description = "ドローン。長く伸びる持続音がゆっくり移ろう、変化の少ない響き"
    description_en = "Ambient drone: long sustained tones that shift very slowly"
    title = "Slow Drone"
    tempo_choices = (60, 62, 64, 66)

    instruments = {
        "drone": _inst("low_drone_bass", GmVoice(program=38)),
        "fifth": _inst("maqam_nay", GmVoice(program=77), name="DroneReed", volume=34),
        "upper": _inst("pad_glass", GmVoice(program=88)),
        "swell": _inst("free_cymbal_swell", GmVoice(program=119)),
    }
    harmony = Harmony(keys=(2, 4, 9), mode="dorian", progressions=PROGRESSIONS, n_progressions=1)
    sections = {
        "d1": Section(intensity=0.2, parts=frozenset({"drone", "fifth", "swell"})),
        "d2": Section(intensity=0.35, parts=frozenset({"drone", "fifth", "swell", "upper"})),
        "d3": Section(intensity=0.5, parts=frozenset({"drone", "fifth", "swell", "upper"})),
        "d4": Section(intensity=0.7, parts=frozenset({"drone", "fifth", "swell", "upper"})),
        "d5": Section(intensity=0.8, parts=frozenset({"drone", "fifth", "swell", "upper"})),
        "d6": Section(intensity=0.6, parts=frozenset({"drone", "fifth", "swell", "upper"})),
        "d7": Section(intensity=0.4, parts=frozenset({"drone", "fifth", "swell", "upper"})),
        "d8": Section(intensity=0.2, parts=frozenset({"drone", "fifth", "swell"})),
    }
    form = ("d1", "d2", "d2", "d3", "d3", "d4", "d4", "d5", "d5", "d6", "d6", "d7", "d8")
    parts = (
        Part("drone", Drone("drone"), pan=128),
        Part("fifth", Drone("fifth", factor=0.8, root_register=(12, 23), interval=7), pan=128),
        Part("upper", UpperTone("upper"), pan=128),
        Part("swell", CymbalSwell("swell"), pan=128),
    )
    mod_channels = {4: 1}
