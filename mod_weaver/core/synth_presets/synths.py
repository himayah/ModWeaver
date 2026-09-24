"""シンセ（第３段階の共有音色。DESIGN.md §12.4）。"""
from __future__ import annotations

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
