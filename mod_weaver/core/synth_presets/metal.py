"""金属の打楽器（ガムランの鍵盤・ゴング、インダストリアルの金属音。DESIGN.md §4.5）。

非調和な部分音（整数倍でない mult）と長い減衰の組合せ。ゴング類は近い部分音（1.0 と 1.006 等）を重ねて
うなりを作る。音程のあるもの（pitched=True）は ``mult`` が基音に対する比率。
"""
from __future__ import annotations

from ..synth import OneShot, Patch
from ._common import HIGH, MID, noise, sweep, tone
from ._registry import register

# ------------------------------------------------------------ ガムラン
GAMELAN_SARON = register("gamelan_saron", Patch(
    "Saron", (tone((1.0, 1.0, 2.2), (2.71, 0.35, 4.5), (5.2, 0.12, 8.0)), noise(weight=0.12, decay=220.0, hp=True)),
    OneShot(1.6), pitched=True, rate_note=MID, volume=46),
    "サロン（ガムランの青銅の鍵盤。非調和部分音 1・2.71・5.2、中程度の減衰）。")

GAMELAN_BONANG = register("gamelan_bonang", Patch(
    "Bonang", (tone((1.0, 1.0, 1.7), (1.52, 0.22, 3.0), (2.34, 0.3, 3.6), (3.4, 0.14, 5.5)),
               noise(weight=0.08, decay=180.0, hp=True)),
    OneShot(1.8), pitched=True, attack_ms=2.0, rate_note=MID, volume=42),
    "ボナン（ガムランの壺型ゴングの列。丸い打音と非調和の響き）。")

GAMELAN_KENONG = register("gamelan_kenong", Patch(
    "Kenong", (tone((1.0, 1.0, 0.8), (1.012, 0.5, 0.8), (2.4, 0.22, 1.7), (3.1, 0.1, 2.6)),),
    OneShot(3.2), pitched=True, attack_ms=4.0, rate_note=MID, volume=44),
    "クノン（大きな壺型ゴング。近い部分音のうなりと長い減衰）。")

GAMELAN_KEMPUL = register("gamelan_kempul", Patch(
    "Kempul", (tone((1.0, 1.0, 0.7), (1.008, 0.6, 0.7), (2.3, 0.2, 1.4), (2.9, 0.12, 2.0), (4.2, 0.06, 3.0)),),
    OneShot(3.0), pitched=True, attack_ms=5.0, rate_note=MID, shift=-12, volume=48),
    "クンプル（吊りゴング。低めの音域で長くうなる）。")

GAMELAN_GONG = register("gamelan_gong", Patch(
    "GongAgeng", (tone((1.0, 1.0, 0.42), (1.006, 0.8, 0.42), (1.53, 0.35, 0.7), (2.34, 0.3, 0.9), (2.83, 0.2, 1.2),
                       (3.67, 0.12, 2.0)),
                  noise(weight=0.06, decay=6.0, lp=0.3)),
    OneShot(5.0), pitched=True, attack_ms=8.0, rate_note=MID, shift=-24, volume=58),
    "ゴン・アグン（大ゴング。超低音のうなりと5秒の減衰。曲の区切り）。")

GAMELAN_KETUK = register("gamelan_ketuk", Patch(
    "Ketuk", (tone((330.0, 1.0, 14.0), (760.0, 0.3, 25.0)), noise(weight=0.2, decay=120.0, lp=0.5)),
    OneShot(0.30), pitched=False, rate_note=MID, volume=38),
    "クトゥッ（小さな壺を止めて打つ短い音）。")

GAMELAN_KENDANG_DHE = register("gamelan_kendang_dhe", Patch(
    "KendangDhe", (sweep(140.0, 95.0, 18.0, 6.0), noise(weight=0.2, decay=40.0, lp=0.4)),
    OneShot(0.40), pitched=False, rate_note=MID, volume=50),
    "クンダン（両面太鼓）の低い音 dhe。")

GAMELAN_KENDANG_TAK = register("gamelan_kendang_tak", Patch(
    "KendangTak", (tone((700.0, 0.6, 40.0)), noise(weight=1.0, decay=45.0, hp=True)),
    OneShot(0.15), pitched=False, rate_note=HIGH, volume=40),
    "クンダンの高く乾いた音 tak。")

# ------------------------------------------------------------ インダストリアル
IND_METAL_CLANG = register("ind_metal_clang", Patch(
    "MetalClang", (tone((420.0, 1.0, 6.0), (987.0, 0.7, 7.0), (1560.0, 0.5, 9.0), (2230.0, 0.35, 11.0),
                        (3310.0, 0.25, 14.0)),
                   noise(weight=0.4, decay=30.0, hp=True)),
    OneShot(0.90), pitched=False, saturate=3.2, rate_note=HIGH, volume=46),
    "金属の打撃（インダストリアル）。非調和の部分音を強く歪ませた硬い音。")

IND_METAL_PIPE = register("ind_metal_pipe", Patch(
    "MetalPipe", (tone((1.0, 1.0, 3.0), (2.61, 0.6, 4.0), (4.9, 0.35, 6.0), (7.3, 0.15, 9.0)),
                  noise(weight=0.1, decay=160.0, hp=True)),
    OneShot(1.0), pitched=True, saturate=2.6, rate_note=MID, volume=44),
    "音程のある金属パイプの打撃（インダストリアルのリフ用。非調和＋強い飽和）。")
