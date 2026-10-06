"""oto.ini の値による切り出し（DESIGN.md §13.5.3.3-3）。"""
from __future__ import annotations

from .otoini import OtoEntry

# cutoff の符号規約（UTAU の流儀。**実音源（重音テト単独音）で確認済み**: wav 652 ms・offset 24・cutoff 73 の「あ」が
# 24〜579 ms の母音になる）:
#   正値: wav の末尾から cutoff ms を捨てる ／ 負値: offset から |cutoff| ms で終える
# （P2 の合成バンクの検証では逆に仮定していた。実音源で直した。DESIGN.md §5.3.3）


def cut_range(e: OtoEntry, n_samples: int, rate: int) -> tuple[int, int]:
    """(開始, 終了) のサンプル位置（終了は含まない）。範囲が空・逆転なら ``(0, 0)``。"""
    ms = rate / 1000.0
    start = max(0, round(e.offset * ms))
    if e.cutoff > 0:
        end = n_samples - round(e.cutoff * ms)
    elif e.cutoff < 0:
        end = start + round(-e.cutoff * ms)
    else:
        end = n_samples
    end = min(end, n_samples)
    return (start, end) if end - start > 1 else (0, 0)


def cut(x: list[float], rate: int, e: OtoEntry) -> tuple[list[float], int]:
    """(切り出した波形, 母音の頭の位置＝preutterance をサンプルに換算した値)。"""
    s, t = cut_range(e, len(x), rate)
    seg = x[s:t]
    pre = min(max(0, round(e.preutterance * rate / 1000.0)), max(0, len(seg) - 1))
    return seg, pre
