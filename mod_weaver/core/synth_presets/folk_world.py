"""世界の民族音楽・ダンス系の楽器（ロシア・ケルト・クレズマー・ムード・バロック。NEW_GENRES_DESIGN.md §3.3）。"""
from __future__ import annotations

from ..synth import Loop, OneShot, Patch
from ._common import MID, loop_harmonics, noise, sweep, tone
from ._registry import register

RU_BALALAIKA = register("ru_balalaika", Patch(
    "Balalaika", (tone((1.0, 1.0, 10.0), (2.0, 0.8, 12.0), (3.0, 0.6, 14.0), (4.0, 0.5, 17.0), (5.0, 0.4, 20.0)),
                  noise(weight=0.1, decay=100.0, hp=True)),
    OneShot(0.35), pitched=True, saturate=1.2, rate_note=MID, volume=46),
    "バラライカ。短く明るい撥弦（トレモロで連打して使う）。")

RU_BAYAN = register("ru_bayan", Patch(
    "Bayan", loop_harmonics(120, ((1, 1.0), (2, 0.7), (3, 0.8), (4, 0.4), (5, 0.5), (6, 0.25), (7, 0.3), (8, 0.15)),
                            detune=0.55),
    Loop(3800, attack_samples=120), pitched=True, rate_note=MID, volume=40),
    "バヤン（ボタン式アコーディオン）。デチューンした2層のリード（うなりの層は 0.55。0.9 だと2つの声が拮抗して基本周波数が一意に測れない〔I4〕）。")

KLEZ_CLARINET = register("klez_clarinet", Patch(
    "Clarinet", loop_harmonics(120, ((1, 1.0), (3, 0.5), (5, 0.3), (7, 0.2), (9, 0.1)), detune=0.15),
    Loop(3800, attack_samples=200), pitched=True, rate_note=MID, volume=44),
    "クラリネット。奇数次倍音のみの木管（クレズマー）。")

CELT_DRONE = register("celt_drone", Patch(
    "Drone", loop_harmonics(120, tuple((h, 1.0 / h ** 0.4) for h in range(1, 11)), detune=0.4),
    Loop(3800, attack_samples=300), pitched=True, shift=-12, rate_note=MID, volume=34),
    "バグパイプ風のドローン。倍音の多い持続低音（shift=-12）。")

CELT_BODHRAN = register("celt_bodhran", Patch(
    "Bodhran", (sweep(150.0, 100.0, 18.0, 9.0), noise(weight=0.4, decay=18.0, lp=0.5)),
    OneShot(0.3), pitched=False, rate_note=MID, volume=54),
    "ボーラン。ヤギ皮のフレームドラム。")

MOOD_STEEL_GTR = register("mood_steel_gtr", Patch(
    "SteelGtr", (tone((1.0, 1.0, 1.6), (2.0, 0.3, 2.5), (3.0, 0.15, 3.5), (4.0, 0.08, 5.0)),),
    OneShot(2.2), pitched=True, peak=0.9, attack_ms=4.0, rate_note=MID, volume=42),
    "ハワイアン・スチールギター。長く伸びるほぼ正弦の音（スライドで使う）。")

MOOD_BONGO = register("mood_bongo", Patch(
    "Bongo", (tone((420.0, 1.0, 28.0), (840.0, 0.3, 38.0)), noise(weight=0.2, decay=50.0, hp=True)),
    OneShot(0.15), pitched=False, rate_note=MID, volume=46),
    "ボンゴ。高く乾いた皮の一打。")

BAROQUE_HARPSICHORD = register("baroque_harpsichord", Patch(
    "Harpsichord", (tone((1.0, 1.0, 6.0), (2.0, 0.9, 8.0), (3.0, 0.7, 10.0), (4.0, 0.7, 12.0), (5.0, 0.5, 14.0),
                         (6.0, 0.4, 16.0), (8.0, 0.3, 20.0)),
                    noise(weight=0.12, decay=150.0, hp=True)),
    OneShot(0.9), pitched=True, saturate=1.1, rate_note=MID, volume=44),
    "チェンバロ。倍音の多いジャックの撥弦と、鋭い打鍵の雑音。")

# ---------------- ラテン・インド（NEW_GENRES 第2弾: samba・raga） ----------------

LATIN_TAMBORIM = register("latin_tamborim", Patch(
    "Tamborim", (tone((1200.0, 1.0, 60.0)), noise(weight=0.6, decay=120.0, hp=True)),
    OneShot(0.08), pitched=False, rate_note=MID, volume=40),
    "タンボリン。小さく高い乾いた一打（サンバ）。")

LATIN_AGOGO_HI = register("latin_agogo_hi", Patch(
    "AgogoHi", (tone((1350.0, 1.0, 22.0), (2300.0, 0.5, 30.0)),),
    OneShot(0.25), pitched=False, rate_note=MID, volume=38),
    "アゴゴ（高）。2つの金属の鐘の高い方。")

LATIN_AGOGO_LO = register("latin_agogo_lo", Patch(
    "AgogoLo", (tone((980.0, 1.0, 22.0), (1750.0, 0.5, 30.0)),),
    OneShot(0.25), pitched=False, rate_note=MID, volume=38),
    "アゴゴ（低）。")

RAGA_TANPURA = register("raga_tanpura", Patch(
    "Tanpura", (tone((1.0, 1.0, 1.2), (2.0, 0.8, 1.4), (3.0, 0.8, 1.6), (4.0, 0.7, 1.8), (5.0, 0.7, 2.0),
                     (6.0, 0.6, 2.4), (7.0, 0.5, 2.8), (8.0, 0.5, 3.2), (9.0, 0.4, 3.6), (10.0, 0.4, 4.0)),),
    OneShot(2.2), pitched=True, attack_ms=6.0, rate_note=MID, volume=36),
    "タンプーラ。倍音が平らで長く響く弦（ジヴァリの「うなり」を倍音の多さで近似）。")

RAGA_SITAR = register("raga_sitar", Patch(
    "Sitar", (tone((1.0, 1.0, 3.0), (2.0, 0.8, 3.5), (3.0, 0.8, 4.0), (4.0, 0.7, 4.5), (5.0, 0.7, 5.0),
                   (6.0, 0.6, 6.0), (7.0, 0.6, 7.0), (8.0, 0.5, 8.0), (9.0, 0.5, 9.0)),
              noise(weight=0.08, decay=100.0, hp=True)),
    OneShot(1.8), pitched=True, saturate=1.4, rate_note=MID, volume=46),
    "シタール風。高次倍音が長く残る撥弦（ジャワリの金属的な響きを飽和で近似）。")

RAGA_TABLA_GE = register("raga_tabla_ge", Patch(
    "TablaGe", (sweep(160.0, 90.0, 12.0, 5.0), noise(weight=0.15, decay=40.0, lp=0.3)),
    OneShot(0.45), pitched=False, rate_note=MID, volume=54),
    "タブラのバヤン（低い方。音程が下がる）。")

RAGA_TABLA_NA = register("raga_tabla_na", Patch(
    "TablaNa", (tone((620.0, 1.0, 18.0), (1240.0, 0.5, 22.0), (1860.0, 0.25, 28.0)),),
    OneShot(0.3), pitched=False, rate_note=MID, volume=44),
    "タブラのダヤン（高い方。澄んで響く）。")

RAGA_TABLA_TIN = register("raga_tabla_tin", Patch(
    "TablaTin", (tone((880.0, 1.0, 35.0), (1760.0, 0.3, 45.0)), noise(weight=0.1, decay=90.0, hp=True)),
    OneShot(0.15), pitched=False, rate_note=MID, volume=40),
    "タブラの縁を叩く短い高音。")
