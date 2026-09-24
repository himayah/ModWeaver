"""各系統モジュールが共有する短縮記法（プリセットの定義を読みやすくするためだけの補助）。"""
from __future__ import annotations

from ..synth import FilterSpec, NoiseLayer, PitchSweepLayer, ToneLayer, WeightedLayer

HIGH = 35      # rate_note=B-3（15.7 kHz）。高域の多い打楽器・効果音用
MID = 24       # rate_note=C-3（8.29 kHz）。既定


def tone(*partials, weight: float = 1.0, lp: float = 0.0, offset_ms: float = 0.0) -> WeightedLayer:
    """``tone((mult, weight, alpha), ...)``。``lp`` > 0 なら one_pole_lp を掛ける。"""
    f = FilterSpec("lp", a=lp) if lp else FilterSpec()
    return WeightedLayer(ToneLayer(tuple(partials), f), weight, offset_ms)


def sweep(f0: float, f1: float, pitch_decay: float, decay: float, weight: float = 1.0) -> WeightedLayer:
    return WeightedLayer(PitchSweepLayer(f0, f1, pitch_decay, decay), weight)


def noise(*, weight: float = 1.0, decay: float | None = None, rise: float | None = None,
          hp: bool = False, lp: float = 0.0) -> WeightedLayer:
    if hp:
        f = FilterSpec("hp")
    elif lp:
        f = FilterSpec("lp", a=lp)
    else:
        f = FilterSpec()
    return WeightedLayer(NoiseLayer(decay_alpha=decay, rise_power=rise, filter=f), weight)


def loop_harmonics(k: int, harmonics: tuple[tuple[int, float], ...], *, detune: float = 0.0) -> tuple[WeightedLayer, ...]:
    """ループ用: 基本サイクル数 ``k`` の倍音 ``(h, weight)``。``detune`` > 0 なら k+1 系の層を重ねてうなりを作る。"""
    main = WeightedLayer(ToneLayer(tuple((k * h, w, None) for h, w in harmonics)))
    if not detune:
        return (main,)
    return main, WeightedLayer(ToneLayer(tuple(((k + 1) * h, w, None) for h, w in harmonics)), detune)
