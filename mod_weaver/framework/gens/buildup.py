"""EDM 系のビルドアップ（FRAMEWORK_REDESIGN.md §7 の ``Buildup``）。現行 ``band_common.buildup()`` と同じ
規則: スネアの連打が 4分→8分→16分→``Retrig`` と加速し、音量が上がる。最後から2つ目の小節の頭に
上昇音（``riser``、約2秒）を置く。現行は別チャンネルの ``riser``/``fx_ch`` を必要としたが、新しい設計では
楽器名だけで区別できるので同じパートに書ける。"""
from __future__ import annotations

from ..context import Generator, MeasureCtx
from ..score import Retrig


class Buildup(Generator):
    def __init__(self, inst: str, riser: str = None, n_measures: int = 4) -> None:
        self.inst = inst
        self.riser = riser
        self.n_measures = n_measures

    def measure(self, m: MeasureCtx) -> None:
        steps = m.m.steps
        phase = m.m.index % self.n_measures
        step = (4, 2, 1, 1)[min(phase, 3)]
        for row in range(0, steps, step):
            vol = min(64, 30 + round(30 * (phase * steps + row) / (self.n_measures * steps)))
            if phase == 3 and row >= steps // 2:
                m.note(row, self.inst, arts=(Retrig(3),))
            else:
                m.note(row, self.inst, vel=vol)
        if self.riser is not None and phase == self.n_measures - 2:
            m.note(0, self.riser, vel=48)
