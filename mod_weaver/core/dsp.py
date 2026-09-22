"""波形・フィルタ・レート算出（設計書 §6.1）。

``clamp`` / ``pad_even`` は旧実装と同名・同挙動（Nostalgic のバイト同一性のため）。
後半の合成プリミティブ（additive / noise_lp / seamless_* など）は新ジャンル専用で、
Nostalgic のサンプル合成は旧式を無改変で使う（D11）。
"""
from __future__ import annotations

import math
import random as _random
from typing import Callable, Iterable, Sequence

from ..errors import SampleConstraintError
from .pitch import PERIODS, hz

CLOCK = 3546895.0  # PAL Amiga クロック（旧 PAL_AMIGA_CLOCK）


def sample_rate(rate_note: int) -> float:
    """tracker note ``rate_note`` で発音したときの再生レート（Hz）。

    C-3 → 8287.14、B-3 → 15694.2、C-2 → 4143.6。
    """
    return CLOCK / (2 * PERIODS[rate_note])


def clamp(x: float) -> int:
    """[-128, 127] へ丸める（旧 ``clamp`` と同一）。"""
    return max(-128, min(127, int(round(x))))


def pad_even(b: bytes) -> bytes:
    """奇数長なら 0x00 を 1 byte 付加して偶数長にする（旧 ``pad_even`` と同一）。"""
    return b if len(b) % 2 == 0 else b + b"\x00"


def to_pcm(values: Iterable[float], gain: float = 127.0) -> bytes:
    """float 列 → 8bit signed PCM（符号なし表現の bytes）。``clamp(v*gain) & 0xFF`` → 偶数長。"""
    return pad_even(bytes(clamp(v * gain) & 0xFF for v in values))


# ============================================================
# 新ジャンル用の波形・エンベロープ・フィルタ（Nostalgic は使わない: D11）
# ============================================================
TWO_PI = 2.0 * math.pi
Partials = Sequence[tuple[float, float]]   # [(倍率 mult, 重み weight)]


def content_spc(rate_note: int, shift: int) -> float:
    """pitched サンプルの 1 周期あたりサンプル数 ``spc = R / F``（設計書 §5.1）。

    ``F = f(rate_note + shift)``（rate_note で発音したとき logical note ``rate_note+shift`` が鳴る）。
    """
    return sample_rate(rate_note) / hz(rate_note + shift)


def additive(f0: float, t: float, partials: Partials, nyquist: float = math.inf) -> float:
    """加算合成 ``Σ w·sin(2π·f0·mult·t)``。``f0*mult`` が ``nyquist`` 以上の項は除外（エイリアス防止）。"""
    total = 0.0
    for mult, weight in partials:
        f = f0 * mult
        if f >= nyquist:
            continue
        total += weight * math.sin(TWO_PI * f * t)
    return total


def partials_saw(n: int) -> list[tuple[float, float]]:
    """ノコギリ波: h=1..n、重み 1/h。"""
    return [(float(h), 1.0 / h) for h in range(1, n + 1)]


def partials_square(n: int) -> list[tuple[float, float]]:
    """矩形波: 奇数 h（≤n）、重み 1/h。"""
    return [(float(h), 1.0 / h) for h in range(1, n + 1, 2)]


def partials_triangle(n: int) -> list[tuple[float, float]]:
    """三角波: 奇数 h（≤n）、重み (−1)^((h−1)/2) / h²。"""
    return [(float(h), (-1.0) ** ((h - 1) // 2) / (h * h)) for h in range(1, n + 1, 2)]


def exp_decay(t: float, alpha: float) -> float:
    """``e^(−αt)``。"""
    return math.exp(-alpha * t)


def adsr(t: float, total: float, a: float, d: float, s: float, r: float) -> float:
    """ADSR（時間は秒）。Attack→Decay→Sustain(s)→Release（total−r から 0 へ）。t<0 または t≥total は 0。"""
    if t < 0 or t >= total:
        return 0.0
    if r > 0 and t >= total - r:
        level = adsr(total - r - 1e-12, total, a, d, s, 0.0)
        return level * (total - t) / r
    if a > 0 and t < a:
        return t / a
    if d > 0 and t < a + d:
        return 1.0 - (1.0 - s) * (t - a) / d
    return s


def noise_lp(rng: _random.Random, n: int, a_start: float, a_end: float) -> list[float]:
    """ホワイトノイズを 1 次 IIR LP に通す（設計書 §6.1）。

    ``y[i] = a[i]·y[i−1] + (1−a[i])·x[i]``、``a[i]`` は ``a_start→a_end`` の線形補間。
    ``a`` が大きいほど暗い（旧スネアの ``lp = lp*0.35 + raw*0.65`` は a=0.35）。``rng`` を n 回消費。
    """
    out: list[float] = []
    y = 0.0
    for i in range(n):
        a = a_start if n == 1 else a_start + (a_end - a_start) * i / (n - 1)
        y = a * y + (1.0 - a) * rng.uniform(-1.0, 1.0)
        out.append(y)
    return out


def one_pole_lp(data: Sequence[float], a: float) -> list[float]:
    """固定係数の 1 次 IIR LP（因果）。``y[i] = a·y[i−1] + (1−a)·x[i]``、``y[−1]=0``。"""
    out: list[float] = []
    y = 0.0
    for x in data:
        y = y * a + x * (1.0 - a)
        out.append(y)
    return out


def diff_hp(data: Sequence[float]) -> list[float]:
    """一次差分 HP（旧ハイハットと同式）。``y[i] = x[i] − x[i−1]``、``x[−1]=0``。"""
    out: list[float] = []
    prev = 0.0
    for x in data:
        out.append(x - prev)
        prev = x
    return out


# ---- 完全ループ ----

def _check_cycles(length: int, k: float, what: str) -> int:
    if abs(k - round(k)) > 1e-9:
        raise SampleConstraintError(f"{what}: cycle count {k} is not an integer (loop would click)")
    k = int(round(k))
    if k < 1 or 2 * k >= length:
        raise SampleConstraintError(f"{what}: cycle count {k} must satisfy 1 <= k < length/2 (length={length})")
    return k


def seamless_terms(length: int, terms: Sequence[tuple[int, float]]) -> list[float]:
    """``terms=[(k_int, weight)]``: 周期数 K を整数で直接指定した和。``x[i] = Σ w·sin(2π·k·i/length)``。"""
    ks = [(_check_cycles(length, k, "seamless_terms"), w) for k, w in terms]
    return [sum(w * math.sin(TWO_PI * k * i / length) for k, w in ks) for i in range(length)]


def seamless_loop(length: int, cycles: int, partials: Partials) -> list[float]:
    """``partials=[(mult, weight)]``。各 ``cycles*mult`` が整数でなければ SampleConstraintError。"""
    terms = []
    for mult, weight in partials:
        k = cycles * mult
        if abs(k - round(k)) > 1e-9:
            raise SampleConstraintError(
                f"seamless_loop: cycles={cycles} * mult={mult} = {k} is not an integer"
            )
        terms.append((int(round(k)), weight))
    return seamless_terms(length, terms)


def circular(filter_fn: Callable[[list[float]], list[float]], body: Sequence[float]) -> list[float]:
    """``body`` を 3 周連結してフィルタを通し、中央の 1 周を返す（ループ境界の連続性を保つ）。"""
    n = len(body)
    filtered = filter_fn(list(body) * 3)
    return filtered[n:2 * n]


def with_attack(body: Sequence[float], attack_len: int) -> list[float]:
    """「アタック部＋ループ本体」（D12）。

    アタック部 = ``body`` の末尾 ``attack_len`` 個 × 半コサイン窓 ``0.5(1−cos(π·i/attack_len))``。
    位相がループ先頭へ連続するため境界にクリックが出ない。``SampleSpec.loop = (attack_len//2, len(body)//2)``。
    """
    n = len(body)
    if attack_len <= 0 or attack_len % 2 != 0 or attack_len > n:
        raise SampleConstraintError(f"with_attack: attack_len must be even and in 2..{n}: {attack_len}")
    tail = body[n - attack_len:]
    attack = [tail[i] * 0.5 * (1.0 - math.cos(math.pi * i / attack_len)) for i in range(attack_len)]
    return attack + list(body)


def loop_design(target_spc: float, l_max: int, k_step: int = 1) -> list[tuple[float, int, int]]:
    """ループ設計の候補 ``(誤差 cent, K, L[偶数])`` を誤差の小さい順に返す（オフライン補助。実行時は定数を使う）。"""
    out = []
    k = k_step
    while k * target_spc <= l_max + target_spc:
        length = 2 * round(k * target_spc / 2)
        if 2 <= length <= l_max:
            cents = 1200.0 * math.log2(k * target_spc / length)
            out.append((cents, k, length))
        k += k_step
    return sorted(out, key=lambda c: (abs(c[0]), c[1]))
