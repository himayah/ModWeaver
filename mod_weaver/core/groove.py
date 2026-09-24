"""タイムベース＆グルーヴ・エンジン（DESIGN.md §4.6、EXT-1）。

- ``SwingConfig``/``apply_swing``: row の偶奇で Speed（``F0x``）を交互に変え、スウィング/シャッフルを
  作る後処理（``profile.post_processors`` から適用する）。1拍=2row（8分音符格子）の timebase を前提にする。
  tracker の BPM（``Fxx``≥0x20）は「24 tick＝1拍」の速さなので、long+short＝24 tick にすると
  ``SongPlan.bpm`` がそのまま4分音符の BPM として鳴る（DESIGN.md §5.5）。
- ``retrigger_param``/``delay_param``: ``E9x``（Retrigger）/``EDx``（Note Delay）の param を返す純粋
  関数（effect は両方とも常に ``0x0E`` 固定なので呼出し側が渡す。``automation.portamento_param`` 等と
  同じ「param のみ返す」規約に揃えている）。1 row 内で複数打を鳴らすサブステップ・ロール用（trap 等）。

挿入は ``CellGrid.insert_command``/``try_insert_command``（core/model.py）に委譲し、チャンネル探索
ロジックを重複させない。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from ..errors import SampleConstraintError
from .model import Pattern

log = logging.getLogger("mod_weaver")


@dataclass(frozen=True)
class SwingConfig:
    long_speed: int = 16    # 偶数 row（拍の表）の Speed
    short_speed: int = 8    # 奇数 row（拍の裏）の Speed。long:short のティック比がスウィング比になる
    # 例: 16:8 = 2:1（純粋3連スウィング）。14:10 = 1.4:1（軽いスウィング）。
    # long+short は 48 / rows_per_beat にする（1拍=24 tick）: 8分格子（1拍=2 row）は 24、16分格子（1拍=4 row）は 12。
    # これ以外だと実際のテンポが表示 BPM からずれる（以前、8分格子の swing-jazz が 7:5＝合計12 で表示の2倍の速さで鳴っていた）

    def __post_init__(self) -> None:
        for v in (self.long_speed, self.short_speed):
            if not 1 <= v <= 31:
                raise SampleConstraintError(f"SwingConfig speed out of range: {v}")


def apply_swing(pattern: Pattern, config: SwingConfig, *, start_row: int = 0) -> None:
    """``pattern`` の ``start_row..rows-1`` に、偶数 row=long_speed／奇数 row=short_speed の
    ``F0x`` を ``CellGrid.insert_command`` で挿入する（偶奇は ``start_row`` からの相対）。

    ``tempo_policy="engine"`` と併用する場合、``apply_tempo``（``F BPM``, param>=32）は
    ``post_processors`` の**後**に row 0 の別チャンネルへ挿入されるため、プロファイルは row 0 に
    2つ目の空き（または note のみで vol/effect なし）のチャンネルを残しておく契約になる
    （DESIGN.md §4.10）。

    4チャンネル全てが同時に vol/effect を持つ row では書き込む先が無い。これは後処理の「装飾」
    であり基本生成を汚染してはならないため（DESIGN.md §4.10）、``ChannelConflictError`` は
    送出せず、その row のみ静かにスキップする（直前の Speed が persist するため、その1 row だけ
    スウィングが掛からない程度の軽微な影響に留まる。頻発する場合はプロファイル側の編成密度を見直す）。
    """
    for row in range(start_row, pattern.rows):
        speed = config.long_speed if (row - start_row) % 2 == 0 else config.short_speed
        if not pattern.try_insert_command(row, 0x0F, speed):
            log.debug("apply_swing: no free channel at row %d, skipping (previous Speed persists)", row)


def retrigger_param(every_ticks: int) -> int:
    """``E9x``: ``every_ticks``（1..15）ティックごとに再トリガする定数音量のロール。
    呼出し側は ``effect=0x0E, param=retrigger_param(...)`` として使う。

    音量を変えたいクレッシェンド・ロールは表現できない（E9x は音量制御を持たない）。その場合は
    行グリッドを細かくして ``composer.articulate``/``composer.ramp`` で1打ずつ別 row に書く。
    """
    if not 1 <= every_ticks <= 15:
        raise SampleConstraintError(f"retrigger ticks out of range: {every_ticks}")
    return 0x90 | every_ticks


def delay_param(ticks: int) -> int:
    """``EDx``: note を ``ticks``（1..15）ティック遅延して発音する。
    呼出し側は ``effect=0x0E, param=delay_param(...)`` として使う。"""
    if not 1 <= ticks <= 15:
        raise SampleConstraintError(f"delay ticks out of range: {ticks}")
    return 0xD0 | ticks
