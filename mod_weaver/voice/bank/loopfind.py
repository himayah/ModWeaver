"""母音ループの検出（VOCAL_DESIGN.md §5.3.3-6）。IT・XM の順方向ループ向けに、継ぎ目へクロスフェードを焼き込む。

方針: 母音部（preutterance 以降）の頭の過渡と末尾の減衰を除いた安定部から、基本周期の整数倍の長さ ``L`` と
始点 ``s`` を、``[s-xf, s)`` と ``[s+L-xf, s+L)`` の差が最小になるように選ぶ。波形は ``s+L`` で打ち切り、
ループ末尾の ``xf`` サンプルを ``[s-xf, s)`` へ向けて混ぜる（ループ末尾→始点が連続になる）。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

MIN_STABLE_MS = 120.0
MIN_LOOP_MS = 80.0


@dataclass(frozen=True)
class LoopResult:
    data: list[float]                  # 打ち切り＋クロスフェード済み（ループ可のとき）。不可なら元の波形のまま
    loop: Optional[tuple[int, int]]    # (開始, 長さ)。不可なら None
    mismatch: Optional[float]          # 継ぎ目の不一致（0=一致。窓の RMS 差 / 窓の RMS）。不可なら None
    reason: str = ""


def _rms(v: list[float]) -> float:
    return (sum(a * a for a in v) / len(v)) ** 0.5 if v else 0.0


def find_loop(x: list[float], rate: int, vowel_start: int, f0: Optional[float]) -> LoopResult:
    n = len(x)
    if not f0:
        return LoopResult(x, None, None, "no F0 (aperiodic)")
    period = rate / f0
    ms = rate / 1000.0
    body = n - vowel_start
    lead, tail = int(0.20 * body), int(0.15 * body)
    r0, r1 = vowel_start + lead, n - tail                      # 安定部 [r0, r1)
    if (r1 - r0) / ms < MIN_STABLE_MS:
        return LoopResult(x, None, None, f"stable part {(r1 - r0) / ms:.0f} ms < {MIN_STABLE_MS:.0f} ms")
    k = max(1, round(MIN_LOOP_MS * ms / period))
    xf = max(8, int(period))
    best = None
    for dl in range(-3, 4):
        L = round(k * period) + dl
        if L < 2 * xf or r0 + xf + L > r1:
            continue
        for s in range(r0 + xf, min(r0 + xf + int(period) + 1, r1 - L + 1)):
            a, b = x[s - xf:s], x[s + L - xf:s + L]
            diff = sum((p - q) ** 2 for p, q in zip(a, b))
            if best is None or diff < best[0]:
                best = (diff, s, L)
    if best is None:
        return LoopResult(x, None, None, "no loop candidate fits in the stable part")
    _, s, L = best
    e = s + L
    ref = x[s - xf:s]
    seg = x[:e]
    for i in range(xf):
        w = (i + 1) / xf
        seg[e - xf + i] = x[e - xf + i] * (1 - w) + ref[i] * w
    window_rms = _rms(x[s + L - xf:s + L]) or 1.0
    mismatch = (best[0] / xf) ** 0.5 / window_rms
    return LoopResult(seg, (s, L), mismatch)
