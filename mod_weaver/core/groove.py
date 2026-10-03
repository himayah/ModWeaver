"""``E9x``（Retrigger）・``EDx``（Note Delay）の param を返す純粋関数（``framework/realize/tracker.py`` が奏法の範囲を検査するのに使う）。

effect は両方とも常に ``0x0E`` 固定なので呼出し側が渡す。1 row 内で複数打を鳴らすサブステップ・ロール用（trap 等）。
スウィング（偶数 step を long、奇数 step を short の Speed にする）は Realizer の責任（``tracker._write_swing``）。
"""
from __future__ import annotations

from ..errors import SampleConstraintError


def retrigger_param(every_ticks: int) -> int:
    """``E9x``: ``every_ticks``（1..15）ティックごとに再トリガする定数音量のロール。
    呼出し側は ``effect=0x0E, param=retrigger_param(...)`` として使う。

    音量を変えたいクレッシェンド・ロールは表現できない（E9x は音量制御を持たない）。その場合は
    step の格子を細かくして 1 打ずつ別の step に書く。
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
