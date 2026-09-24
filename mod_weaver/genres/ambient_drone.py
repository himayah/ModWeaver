"""ambient-drone: アンビエント・ドローン風（DESIGN.md §6.16.33）。A4（4ch、Amiga 互換）: 低い主音のドローン、
5度の持続音、8小節ごとに1音だけ変わる上の音、4小節ごとのシンバルのスウェル。旋律・打楽器なし。

起伏は音量の大きな弧（intensity 0.2→0.8→0.2）と、4小節周期の音量のうねり（持続音への音量セル）で作る。"""
from __future__ import annotations

import math

from ..core.midi import GmVoice
from ..core.model import Cell, ChordSpec
from ..core.pitch import MODES, fold_into_range
from ..profiles.band_common import BandProfile, ChannelDef, Section, preset
from ..profiles.registry import register_profile

C = ChordSpec
CH_DRONE, CH_FIFTH, CH_UPPER, CH_SWELL = range(4)
UPPER_REGISTER = (24, 35)
SWELL_ROWS = (4, 8, 12)                        # 持続音の音量を書き換える row（1小節に3回）

# 区間 → (intensity, 上の音の主音からの音階の段。None なら鳴らさない)
ARC = {
    "d1": (0.2, None), "d2": (0.35, 2), "d3": (0.5, 4), "d4": (0.7, 6), "d5": (0.8, 5),
    "d6": (0.6, 3), "d7": (0.4, 1), "d8": (0.2, None),
}


@register_profile
class AmbientDroneProfile(BandProfile):
    id = "ambient-drone"
    category = "style"
    display_name = "Ambient Drone"
    description = "ドローン。長く伸びる持続音がゆっくり移ろう、変化の少ない響き"
    description_en = "Ambient drone: long sustained tones that shift very slowly"
    title = "Slow Drone"
    default_filename = "AmbientDrone.mod"
    tempo_choices = (60, 62, 64, 66)

    KIT = (
        ("drone", preset("low_drone_bass")), ("fifth", preset("maqam_nay", name="DroneReed", volume=34)),
        ("upper", preset("pad_glass")), ("swell", preset("free_cymbal_swell")),
    )
    GM = {"fifth": GmVoice(program=77)}
    CHANNELS = (
        ChannelDef("drone", ("drone",)),
        ChannelDef("fifth", ("fifth",)),
        ChannelDef("upper", ("upper",)),
        ChannelDef("swell", ("swell",)),
    )
    KEYS = (2, 4, 9)
    MODE = "dorian"
    PROGRESSIONS = (("i drone", (C(0, "min", label="i"),)),)
    N_PROGRESSIONS = 1
    SECTIONS = {k: Section(k, intensity=i, parts=frozenset({"drone"} | ({"upper"} if d is not None else set())))
                for k, (i, d) in ARC.items()}
    # 各区間 8小節（2 pattern）。上の音は8小節ごとに1音だけ変わる
    FORM = ("d1", "d2", "d2", "d3", "d3", "d4", "d4", "d5", "d5", "d6", "d6", "d7", "d8")

    def compose_measure(self, mctx, st, rng, buf):
        sec = self.SECTIONS[mctx.pattern.kind]
        ins = mctx.instruments
        tonic = mctx.pattern.extra["tonic"]
        base = 20 + 36 * sec.intensity
        # 4小節周期のうねり（0.75〜1.0 倍）
        def level(row: int) -> int:
            phase = (mctx.measure_idx * 16 + row) / 64.0
            return max(1, min(64, round(base * (0.875 - 0.125 * math.cos(2 * math.pi * phase)))))

        root = fold_into_range(tonic, 0, 11)
        fifth = fold_into_range(tonic + 7, 12, 23)
        degree = ARC[sec.kind][1]
        if mctx.measure_idx == 0:
            buf.put(0, CH_DRONE, ins["drone"].cell(root, vol=level(0)))
            buf.put(0, CH_FIFTH, ins["fifth"].cell(fifth, vol=round(level(0) * 0.8)))
            if degree is None:
                buf.put(0, CH_UPPER, ins["upper"].off())
            else:
                steps = MODES[self.MODE]
                pc = (tonic + steps[degree % len(steps)]) % 12
                buf.put(0, CH_UPPER, ins["upper"].cell(fold_into_range(pc, *UPPER_REGISTER), vol=round(level(0) * 0.7)))
        for row in SWELL_ROWS:
            v = level(row)
            buf.put(row, CH_DRONE, Cell(None, 0, vol=v))
            buf.put(row, CH_FIFTH, Cell(None, 0, vol=round(v * 0.8)))
            if degree is not None:
                buf.put(row, CH_UPPER, Cell(None, 0, vol=round(v * 0.7)))
        if mctx.measure_idx == 2 and sec.intensity >= 0.5:
            buf.put(0, CH_SWELL, ins["swell"].cell(vol=round(20 + 20 * sec.intensity)))
