"""日本・沖縄の楽器（雅楽・沖縄民謡・演歌・浪曲・出囃子。NEW_GENRES_DESIGN.md §3.3）。

「風」の音色で、実楽器の再現ではない。ループは K=120（shift=0 で C4 付近）・L=3800（orch・wind と同じ）、
無音程の打楽器は ``tone`` の第1引数を周波数（Hz）として使う（``perc.py`` と同じ）。
"""
from __future__ import annotations

from ..synth import Loop, OneShot, Patch
from ._common import MID, HIGH, loop_harmonics, noise, tone
from ._registry import register

# ---------------- 管（ループ） ----------------

JP_SHO = register("jp_sho", Patch(
    "Sho", loop_harmonics(120, ((1, 1.0), (2, 0.9), (3, 0.8), (4, 0.6), (5, 0.5), (6, 0.4)), detune=0.5),
    Loop(3800, attack_samples=400), pitched=True, rate_note=MID, volume=40),
    "笙。倍音が平らに揃った持続音（合竹の1音ぶん）。わずかなうなり。")

JP_HICHIRIKI = register("jp_hichiriki", Patch(
    "Hichiriki", loop_harmonics(120, ((1, 1.0), (2, 0.5), (3, 1.0), (4, 0.5), (5, 0.9), (6, 0.4), (7, 0.6), (9, 0.3)),
                                detune=0.25),
    Loop(3800, attack_samples=150), pitched=True, rate_note=MID, volume=44),
    "篳篥。奇数次倍音が強く鼻にかかったダブルリード風の音。")

JP_RYUTEKI = register("jp_ryuteki", Patch(
    "Ryuteki", loop_harmonics(120, ((1, 1.0), (2, 0.35), (3, 0.15), (4, 0.06)), detune=0.2),
    Loop(3800, attack_samples=250), pitched=True, shift=12, rate_note=MID, volume=40),
    "龍笛・篠笛。高い横笛（shift=+12）。")

JP_SHAKUHACHI = register("jp_shakuhachi", Patch(
    "Shakuhachi", loop_harmonics(120, ((1, 1.0), (2, 0.2), (3, 0.3), (4, 0.08), (5, 0.1)), detune=0.4),
    Loop(3800, attack_samples=500), pitched=True, rate_note=MID, volume=42),
    "尺八。基音が太く息の多い縦笛。")

# ---------------- 撥弦（ワンショット） ----------------

JP_BIWA = register("jp_biwa", Patch(
    "Biwa", (tone((1.0, 1.0, 5.0), (2.0, 0.7, 7.0), (3.0, 0.5, 9.0), (4.0, 0.4, 12.0), (5.0, 0.3, 15.0)),
             noise(weight=0.15, decay=80.0, hp=True)),
    OneShot(1.2), pitched=True, saturate=1.2, rate_note=MID, volume=46),
    "琵琶。撥の打撃と長めの余韻。")

JP_SHAMISEN = register("jp_shamisen", Patch(
    "Shamisen", (tone((1.0, 1.0, 7.0), (2.0, 0.8, 9.0), (3.0, 0.7, 11.0), (4.0, 0.6, 14.0), (5.0, 0.5, 17.0),
                      (6.0, 0.4, 20.0), (7.0, 0.3, 25.0)), noise(weight=0.25, decay=60.0, hp=True)),
    OneShot(0.6), pitched=True, saturate=1.3, rate_note=MID, volume=46),
    "三味線。撥の打撃音と、さわり（共鳴の唸り）を思わせる高次倍音。")

JP_KOTO = register("jp_koto", Patch(
    "Koto", (tone((1.0, 1.0, 4.0), (2.0, 0.5, 5.0), (3.0, 0.3, 7.0), (4.0, 0.2, 9.0)),
             noise(weight=0.08, decay=120.0, hp=True)),
    OneShot(1.4), pitched=True, rate_note=MID, volume=44),
    "箏。爪で弾いた余韻の長い撥弦。")

OKI_SANSHIN = register("oki_sanshin", Patch(
    "Sanshin", (tone((1.0, 1.0, 8.0), (2.0, 0.6, 10.0), (3.0, 0.5, 13.0), (4.0, 0.3, 16.0)),
                noise(weight=0.12, decay=90.0, hp=True)),
    OneShot(0.5), pitched=True, saturate=1.15, rate_note=MID, volume=46),
    "三線。蛇皮の乾いた撥弦。三味線より丸く短い。")

# ---------------- 打楽器・金属（無音程） ----------------

JP_KAKKO = register("jp_kakko", Patch(
    "Kakko", (tone((330.0, 1.0, 40.0), (660.0, 0.4, 50.0)), noise(weight=0.6, decay=60.0, hp=True)),
    OneShot(0.12), pitched=False, rate_note=MID, volume=44),
    "鞨鼓。小さな両面太鼓の乾いた連打。")

JP_SHOKO = register("jp_shoko", Patch(
    "Shoko", (tone((1180.0, 1.0, 18.0), (1760.0, 0.6, 22.0), (2490.0, 0.5, 28.0), (3300.0, 0.3, 35.0)),),
    OneShot(0.5), pitched=False, rate_note=HIGH, volume=40),
    "鉦鼓。小さな金属の皿を叩く澄んだ音。")

JP_KANE = register("jp_kane", Patch(
    "Atarigane", (tone((2100.0, 1.0, 20.0), (3150.0, 0.7, 26.0), (4300.0, 0.4, 35.0)),),
    OneShot(0.35), pitched=False, rate_note=HIGH, volume=40),
    "当たり鉦。高く短い金属音（出囃子・祭囃子）。")

JP_SHIME = register("jp_shime", Patch(
    "ShimeDaiko", (tone((260.0, 1.0, 25.0)), noise(weight=0.5, decay=30.0, hp=True)),
    OneShot(0.15), pitched=False, saturate=1.2, rate_note=MID, volume=52),
    "締太鼓。張りの強い鋭い一打。")

OKI_PARANKUU = register("oki_parankuu", Patch(
    "Parankuu", (tone((220.0, 1.0, 22.0), (440.0, 0.3, 30.0)), noise(weight=0.35, decay=35.0, lp=0.4)),
    OneShot(0.2), pitched=False, rate_note=MID, volume=50),
    "パーランクー。片面の小さなフレームドラム。")

OKI_SANBA = register("oki_sanba", Patch(
    "Sanba", (noise(weight=1.0, decay=120.0, hp=True), tone((1800.0, 0.5, 90.0))),
    OneShot(0.06), pitched=False, rate_note=HIGH, volume=36),
    "三板。木片を打ち合わせる乾いたカチッという音。")
