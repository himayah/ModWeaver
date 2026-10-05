"""窓付き sinc のリサンプリング（純 Python。取り込み時だけ使う。VOCAL_DESIGN.md §5.3.3-5）。"""
from __future__ import annotations

import math


def resample(x: list[float], src: int, dst: int, taps: int = 12) -> list[float]:
    if src == dst or not x:
        return list(x)
    ratio = dst / src
    n_out = int(len(x) * ratio)
    cutoff = min(1.0, ratio)                      # 縮小のときはエイリアス防止で帯域を絞る
    half = taps / cutoff if cutoff < 1 else taps
    out = []
    n = len(x)
    for j in range(n_out):
        pos = j / ratio
        lo, hi = int(math.floor(pos - half)) + 1, int(math.floor(pos + half))
        acc = 0.0
        for i in range(max(lo, 0), min(hi, n - 1) + 1):
            d = (i - pos) * cutoff
            if d == 0:
                s = 1.0
            else:
                s = math.sin(math.pi * d) / (math.pi * d)
            w = 0.5 + 0.5 * math.cos(math.pi * (i - pos) / half)       # Hann 窓
            acc += x[i] * s * w * cutoff
        out.append(acc)
    return out
