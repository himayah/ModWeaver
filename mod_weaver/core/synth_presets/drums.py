"""ドラム（第３段階の共有音色。DESIGN.md §12.4）。"""
from __future__ import annotations

from ..synth import FilterSpec, OneShot, Patch
from ._common import HIGH, MID, noise, sweep, tone
from ._registry import register

DRUM_POP_KICK = register("drum_pop_kick", Patch(
    "PopKick", (sweep(130.0, 50.0, 30.0, 10.0), noise(weight=0.1, decay=2000.0)),
    OneShot(0.30), pitched=False, saturate=1.3, rate_note=MID, volume=60),
    "現代ポップの丸いキック。130Hz から 50Hz へのピッチドロップ＋短いクリック。")

DRUM_POP_SNARE = register("drum_pop_snare", Patch(
    "PopSnare", (tone((200.0, 1.0, 22.0), weight=0.5), noise(weight=0.7, decay=14.0, lp=0.2)),
    OneShot(0.25), pitched=False, saturate=1.3, rate_note=MID, volume=50),
    "胴鳴り 200Hz＋やや明るいノイズのポップスのスネア。")

DRUM_GATED_SNARE = register("drum_gated_snare", Patch(
    "GatedSnare", (tone((180.0, 1.0, 8.0), weight=0.5), noise(weight=1.0, decay=3.0, hp=True)),
    OneShot(0.35), pitched=False, tail_fade_ms=40.0, saturate=1.8, rate_note=MID, volume=54),
    "80年代のゲート・スネア。長く鳴るノイズを途中で急に切る（tail_fade）大きなスネア。")

DRUM_909_KICK = register("drum_909_kick", Patch(
    "Kick909", (sweep(180.0, 48.0, 22.0, 5.0), noise(weight=0.12, decay=1800.0)),
    OneShot(0.50), pitched=False, saturate=1.6, rate_note=MID, volume=62),
    "909 系の4つ打ちキック。長めのピッチドロップと余韻。house/techno/edm 用。")

DRUM_909_HAT = register("drum_909_hat", Patch(
    "Hat909", (noise(decay=45.0, hp=True), tone((5200.0, 0.3, 40.0), (6800.0, 0.2, 45.0), weight=0.4)),
    OneShot(0.09), pitched=False, post_filter=FilterSpec("hp"), rate_note=HIGH, volume=40),
    "909 系のクローズド・ハイハット。金属的な HP ノイズの短い音。")

DRUM_909_OPEN_HAT = register("drum_909_open_hat", Patch(
    "OpenHat909", (noise(decay=9.0, hp=True), tone((5200.0, 0.3, 8.0), (6800.0, 0.2, 9.0), weight=0.4)),
    OneShot(0.45), pitched=False, post_filter=FilterSpec("hp"), rate_note=HIGH, volume=38),
    "909 系のオープン・ハイハット（裏拍用）。")

DRUM_RIM = register("drum_rim", Patch(
    "Rimshot", (tone((1650.0, 1.0, 60.0), (3200.0, 0.4, 80.0)), noise(weight=0.3, decay=120.0, hp=True)),
    OneShot(0.06), pitched=False, rate_note=HIGH, volume=44),
    "乾いたリムショット／クロススティック。bossa のクラーベや lo-fi のスネア代わり。")

DRUM_TOM = register("drum_tom", Patch(
    "Tom", (sweep(140.0, 118.0, 70.0, 9.0), noise(weight=0.1, decay=900.0)),
    OneShot(0.40), pitched=True, saturate=1.2, rate_note=MID, volume=50),
    "音程のあるタム（pitched。note で高さを変えてフィルに使う）。")

DRUM_BOOMBAP_KICK = register("drum_boombap_kick", Patch(
    "BoomBapKick", (sweep(100.0, 48.0, 25.0, 9.0), noise(weight=0.15, decay=600.0, lp=0.5)),
    OneShot(0.35), pitched=False, saturate=1.8, rate_note=MID, volume=62),
    "ブーンバップ／ローファイの太く歪んだキック。")

DRUM_BOOMBAP_SNARE = register("drum_boombap_snare", Patch(
    "BoomBapSnare", (tone((185.0, 1.0, 18.0), weight=0.5), noise(weight=0.8, decay=12.0, lp=0.3)),
    OneShot(0.30), pitched=False, saturate=1.6, rate_note=MID, volume=52),
    "ブーンバップの湿ったスネア（LP ノイズで暗め）。")
