"""oto.ini の値による切り出し（VOCAL_DESIGN.md §5.3.3-3）。"""
from __future__ import annotations

from .otoini import OtoEntry

# cutoff の符号規約（UTAU の流儀。実音源での確認は P2 の受け入れ項目。違えばここだけ直す）:
#   負値: wav の末尾から |cutoff| ms を捨てる ／ 正値: offset から cutoff ms で終える
CUTOFF_POSITIVE_FROM_OFFSET = True


def cut_range(e: OtoEntry, n_samples: int, rate: int) -> tuple[int, int]:
    """(開始, 終了) のサンプル位置（終了は含まない）。範囲が空・逆転なら ``(0, 0)``。"""
    ms = rate / 1000.0
    start = max(0, round(e.offset * ms))
    if e.cutoff < 0:
        end = n_samples - round(-e.cutoff * ms)
    elif e.cutoff > 0:
        end = start + round(e.cutoff * ms) if CUTOFF_POSITIVE_FROM_OFFSET else round(e.cutoff * ms)
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
