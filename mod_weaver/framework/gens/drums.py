"""ドラムの型（FRAMEWORK_REDESIGN.md §7 の ``Groove``）。現行 ``band_common`` の ``Hit``・``hits()``・
``BandProfile.drums`` と同じ値・規則で、座標を row ではなく step で書く。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping, Optional, Sequence

from ...errors import PlanError
from ..context import Generator, MeasureCtx
from ..plan import SectionPlan
from ..score import Delay


@dataclass(frozen=True)
class Hit:
    row: int                                    # step
    key: str                                    # 楽器名
    vol: int
    prob: float = 1.0
    note: Optional[float] = None                # 音程のある楽器（タム等）の書かれた音高。無ければ None


GroovePattern = tuple[Hit, ...]   # grooves マッピングの値の型。Generator クラスは下の Groove（名前が重なるが
# 設計書 §7 の表の名前どおりにしてある。型エイリアスは別名にして衝突を避ける）


def hits(key: str, rows: Sequence[int], vol: int, prob: float = 1.0,
         notes: Optional[Sequence[float]] = None) -> tuple[Hit, ...]:
    """同じ楽器の打点の列。音程のある楽器は ``notes``（``rows`` と同じ長さ）で各打点の音高を与える。"""
    if notes is not None and len(notes) != len(rows):
        raise PlanError(f"hits({key!r}): {len(rows)} rows but {len(notes)} notes")
    return tuple(Hit(r, key, vol, prob, None if notes is None else notes[i]) for i, r in enumerate(rows))


def _default_groove_name(plan: SectionPlan) -> str:
    return plan.section.groove


class Groove(Generator):
    """区間の ``groove``（``Section.groove``）の型を鳴らす。``Section.fill`` なら最後の小節の後半を
    ``"fill"`` に差し替え、``Section.crash`` なら最初の小節に ``"crash"`` を足す（現行どおり）。"""

    def __init__(self, grooves: Mapping[str, GroovePattern], *, late: Mapping[str, float] = None,
                 humanize: int = 4, groove_name: Callable[[SectionPlan], str] = _default_groove_name) -> None:
        self.grooves = grooves
        self.late = dict(late or {})
        self.humanize = humanize
        self.groove_name = groove_name

    def measure(self, m: MeasureCtx) -> None:
        sec = m.plan.section
        name = self.groove_name(m.plan)
        groove = list(self.grooves[name])
        if sec.fill and m.is_last and "fill" in self.grooves:
            half = m.m.steps // 2
            groove = [h for h in groove if h.row < half] + list(self.grooves["fill"])
        if sec.crash and m.is_first and "crash" in self.grooves:
            groove = groove + list(self.grooves["crash"])
        for h in groove:
            if h.row >= m.m.steps:
                continue
            if h.prob < 1.0 and m.rng.random() >= h.prob:
                continue
            if h.key in self.late and m.rng.random() < self.late[h.key]:
                m.note(h.row, h.key, h.note, arts=(Delay(m.rng.randint(1, 2)),))
            else:
                j = m.rng.randint(-self.humanize, self.humanize) if self.humanize else 0
                m.note(h.row, h.key, h.note, vel=m.scale_drum(h.vol + j))
