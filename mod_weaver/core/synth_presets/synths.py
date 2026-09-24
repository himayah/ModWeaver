"""シンセ（第３段階の共有音色。DESIGN.md §4.5）。"""
from __future__ import annotations

import math

from ..synth import FilterSpec, Loop, OneShot, Patch
from ._common import MID, loop_harmonics, tone
from ._registry import register

SYN_SAW_LEAD = register("syn_saw_lead", Patch(
    "SawLead", loop_harmonics(6, tuple((h, 1.0 / h) for h in range(1, 9))),
    Loop(190, attack_samples=40), pitched=True, rate_note=MID, volume=46),
    "ノコギリ波のリード（ループ。synthwave・edm）。")

SYN_SQUARE_LEAD = register("syn_square_lead", Patch(
    "SquareLead", loop_harmonics(6, ((1, 1.0), (3, 1 / 3), (5, 1 / 5), (7, 1 / 7), (9, 1 / 9))),
    Loop(190, attack_samples=30), pitched=True, rate_note=MID, volume=44),
    "矩形波のリード（ループ。チップチューン風の明るい旋律）。")

SYN_PLUCK = register("syn_pluck", Patch(
    "SynthPluck", (tone(*((float(h), 1.0 / h, 6.0 + 2 * h) for h in range(1, 9))),),
    OneShot(0.50), pitched=True, post_filter=FilterSpec("lp", a=0.3), rate_note=MID, volume=46),
    "シンセのプラック（アルペジオ・短い旋律）。")

SYN_ARP_BELL = register("syn_arp_bell", Patch(
    "ArpBell", (tone((1.0, 1.0, 6.0), (2.0, 0.3, 9.0), (4.0, 0.2, 12.0), (7.0, 0.1, 20.0)),),
    OneShot(0.50), pitched=True, rate_note=MID, volume=44),
    "ガラスのようなアルペジオ用ベル・シンセ。")

SYN_BRASS = register("syn_brass", Patch(
    "SynthBrass", loop_harmonics(6, ((1, 1.0), (2, 0.7), (3, 0.5), (4, 0.35), (5, 0.25), (6, 0.15))),
    Loop(190, attack_samples=60), pitched=True, rate_note=MID, volume=46),
    "80年代のシンセ・ブラス（ループ。city-pop・jpop-80s の旋律と決め）。")

SYN_STAB = register("syn_stab", Patch(
    "SynthStab", (tone(*((float(h), 1.0 / h, 12.0) for h in range(1, 7))),),
    OneShot(0.25), pitched=True, post_filter=FilterSpec("lp", a=0.4), rate_note=MID, volume=44),
    "短いシンセ・スタブ（techno のシーケンス）。")

SYN_POLY_PAD = register("syn_poly_pad", Patch(
    "PolyPad", loop_harmonics(120, tuple((h, 1.0 / h) for h in range(1, 7)), detune=0.7),
    Loop(3800, attack_samples=600), pitched=True, rate_note=MID, volume=38),
    "80年代のポリシンセ・パッド（隣接整数デチューンの2層ループ）。")

# ------------------------------------------------------------ チップチューン（ファミコン風の音源）
# パルス波のデューティ d の倍音 n の振幅は |sin(π n d)| / n。K=12・L=380 は K=6・L=190 と同じ高さで、15 倍音まで入る。
CHIP_PULSE25 = register("chip_pulse25", Patch(
    "Pulse25", loop_harmonics(12, tuple((h, abs(math.sin(math.pi * h * 0.25)) / h) for h in range(1, 16)
                                        if abs(math.sin(math.pi * h * 0.25)) > 1e-9)),
    Loop(380, attack_samples=8), pitched=True, rate_note=MID, volume=40),
    "パルス波 25%（チップチューンの旋律。明るい整数倍音）。")

CHIP_PULSE12 = register("chip_pulse12", Patch(
    "Pulse12", loop_harmonics(12, tuple((h, abs(math.sin(math.pi * h * 0.125)) / h) for h in range(1, 16)
                                        if abs(math.sin(math.pi * h * 0.125)) > 1e-9)),
    Loop(380, attack_samples=8), pitched=True, rate_note=MID, volume=34),
    "パルス波 12.5%（チップチューンのアルペジオ。細く明るい）。")

CHIP_TRIANGLE = register("chip_triangle", Patch(
    "Triangle", loop_harmonics(3, ((1, 1.0), (3, 1 / 9), (5, 1 / 25), (7, 1 / 49))),
    Loop(190), pitched=True, rate_note=MID, shift=-12, volume=52),
    "三角波（チップチューンのベース。純音に近い低音）。")

# ------------------------------------------------------------ インダストリアル
IND_BUZZ_LEAD = register("ind_buzz_lead", Patch(
    "BuzzLead", loop_harmonics(6, ((1, 1.0), (3, 1 / 3), (5, 1 / 5), (7, 1 / 7), (9, 1 / 9))),
    Loop(190, attack_samples=20), pitched=True, saturate=2.5, rate_note=MID, volume=40),
    "強く歪ませた矩形波のリード（インダストリアル）。")
