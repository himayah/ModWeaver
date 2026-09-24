"""効果音（第３段階の共有音色。DESIGN.md §4.5）。ノイズはループにできないので、長い OneShot を小節頭で鳴らし直す。"""
from __future__ import annotations

from ..synth import OneShot, Patch
from ._common import HIGH, MID, noise, sweep, tone
from ._registry import register

FX_VINYL = register("fx_vinyl", Patch(
    "VinylNoise", (noise(weight=0.8, lp=0.6), noise(weight=0.25, hp=True)),
    OneShot(3.0), pitched=False, attack_ms=30.0, tail_fade_ms=30.0, rate_note=MID, volume=14),
    "レコードのヒスノイズ（lo-fi の背景）。2小節ほどで鳴らし直す。")

FX_RAIN = register("fx_rain", Patch(
    "Rain", (noise(lp=0.8),), OneShot(3.0), pitched=False, attack_ms=50.0, tail_fade_ms=50.0,
    rate_note=MID, volume=16),
    "雨音のような柔らかい LP ノイズ（lo-fi chill の環境音）。")

FX_RISER = register("fx_riser", Patch(
    "Riser", (noise(weight=0.8, rise=2.5, hp=True), sweep(200.0, 1400.0, 0.8, None, weight=0.4)),
    OneShot(2.0), pitched=False, tail_fade_ms=20.0, rate_note=MID, volume=44),
    "盛り上げの上昇音（上昇する HP ノイズ＋上がっていく音程）。")

FX_IMPACT = register("fx_impact", Patch(
    "Impact", (sweep(120.0, 35.0, 6.0, 2.5), noise(weight=0.6, decay=4.0, lp=0.5)),
    OneShot(2.0), pitched=False, saturate=1.5, rate_note=MID, volume=64),
    "低い衝撃音（ドロップ頭・予告編の一撃）。")

FX_JUMP = register("fx_jump", Patch(
    "ChipJump", (sweep(300.0, 1400.0, 20.0, 8.0), sweep(600.0, 2800.0, 20.0, 8.0, weight=0.35)),
    OneShot(0.25), pitched=False, rate_note=HIGH, volume=36),
    "上昇ピッチの「ジャンプ音」（チップチューンの効果音。2本の上昇スイープ）。")

FX_FACTORY = register("fx_factory", Patch(
    "FactoryNoise", (noise(lp=0.6), tone((55.0, 0.4, 0.05), (110.0, 0.2, 0.05))),
    OneShot(3.8), pitched=False, attack_ms=150.0, tail_fade_ms=200.0, saturate=1.6, rate_note=MID, volume=24),
    "工場の騒音（一定のノイズと低いうなり。インダストリアルで小節頭に鳴らし直す）。")
