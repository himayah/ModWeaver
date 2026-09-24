"""パーカッション（第３段階の共有音色。DESIGN.md §12.4）。"""
from __future__ import annotations

from ..synth import OneShot, Patch
from ._common import HIGH, MID, noise, sweep, tone
from ._registry import register

PERC_SHAKER = register("perc_shaker", Patch(
    "Shaker", (noise(decay=30.0, hp=True),), OneShot(0.12), pitched=False, attack_ms=12.0,
    rate_note=HIGH, volume=30),
    "シェイカー。立ち上がりの柔らかい HP ノイズ。")

PERC_TAMBOURINE = register("perc_tambourine", Patch(
    "Tambourine", (tone((4200.0, 0.4, 18.0), (5300.0, 0.3, 20.0), (6700.0, 0.25, 24.0)),
                   noise(weight=0.6, decay=14.0, hp=True)),
    OneShot(0.30), pitched=False, rate_note=HIGH, volume=34),
    "タンバリン。鈴の非調和部分音＋ HP ノイズ。")

PERC_CONGA = register("perc_conga", Patch(
    "Conga", (sweep(260.0, 210.0, 40.0, 12.0), noise(weight=0.15, decay=300.0)),
    OneShot(0.30), pitched=True, rate_note=MID, volume=44),
    "コンガ（pitched。note で高低を打ち分ける）。")

PERC_CLAVE = register("perc_clave", Patch(
    "Clave", (tone((2500.0, 1.0, 35.0), (3700.0, 0.3, 50.0)),), OneShot(0.12), pitched=False,
    rate_note=HIGH, volume=40),
    "クラーベ。硬い木の短い音。")

PERC_CAJON = register("perc_cajon", Patch(
    "CajonLow", (sweep(110.0, 70.0, 30.0, 12.0), noise(weight=0.5, decay=20.0, lp=0.4)),
    OneShot(0.35), pitched=False, rate_note=MID, volume=54),
    "カホンの低音（キック代わり）。")

PERC_CAJON_SLAP = register("perc_cajon_slap", Patch(
    "CajonSlap", (tone((400.0, 0.5, 30.0)), noise(weight=1.0, decay=25.0, hp=True)),
    OneShot(0.20), pitched=False, rate_note=MID, volume=46),
    "カホンの高音（スネア代わり）。")

PERC_SURDO = register("perc_surdo", Patch(
    "Surdo", (sweep(80.0, 62.0, 12.0, 4.0),), OneShot(0.80), pitched=False, rate_note=MID, volume=50),
    "スルド（ボサノバ・サンバの低い太鼓）。")

PERC_TAIKO = register("perc_taiko", Patch(
    "Taiko", (sweep(95.0, 48.0, 10.0, 3.5), noise(weight=0.4, decay=8.0, lp=0.5)),
    OneShot(1.40), pitched=False, saturate=1.4, rate_note=MID, volume=64),
    "和太鼓／大太鼓の重い一撃（trailer・dark-tense）。")

PERC_STOMP = register("perc_stomp", Patch(
    "Stomp", (sweep(90.0, 55.0, 25.0, 12.0), noise(weight=0.5, decay=18.0, lp=0.5)),
    OneShot(0.30), pitched=False, rate_note=MID, volume=56),
    "足踏み（フォークのキック代わり）。")
