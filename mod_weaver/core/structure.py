"""可変小節・ポリメトリック補助（CORE_EXTENSION_DESIGN §4.2、EXT-2）。

可変長 measure と ``D00`` 自動挿入そのものは ``model.ChordSlot.rows``／``GenreProfile.variable_meter``／
``engine.compose_song`` の側で完結しており、本モジュールに専用クラスは無い（設計段階の簡略化。
CORE_EXTENSION_DESIGN §0 参照）。ポリメトリック合成（minimalism 等）向けの折返しヘルパーのみを置く。
"""
from __future__ import annotations

from ..errors import PlanError


def polymetric_row(row: int, cycle_rows: int) -> int:
    """``row`` をチャンネル固有の周期 ``cycle_rows`` に折り返す（``row % cycle_rows``）。

    「1 measure = 複数チャンネルの周期の最小公倍数（LCM）行数」として ``ChordSlot(rows=lcm)`` を
    与えたとき、チャンネルごとに独立した固定パターンを ``polymetric_row(row, cycle_rows)`` で
    引いた行インデックスから生成する。
    """
    if cycle_rows <= 0:
        raise PlanError(f"cycle_rows must be positive: {cycle_rows}")
    return row % cycle_rows
