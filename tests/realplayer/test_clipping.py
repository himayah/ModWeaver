"""全ジャンル・全トラッカー形式を実プレイヤー（libopenmpt）で再生し、音割れしない（最大振幅 < 0 dBFS）ことを検査する。

verify の V15（左右の同時合計音量 ≤ 120）はチャンネル音量の単純合計による目安で、実際の再生エンジンのミキシング
（チャンネル数に応じたヘッドルーム、サンプル波形の振幅）を考えない。その代わりに本テストが全ジャンルの音割れを実測で確かめる。
"""
import dataclasses

import pytest

from mod_weaver import engine
from mod_weaver.core import native, native_level
from mod_weaver.framework.compose import compose, resolve_plan
from mod_weaver.framework.realize.tracker import realize
from mod_weaver.framework.target import resolve
from tests.realplayer import peak, requires_openmpt

pytestmark = requires_openmpt

TRACKER_FORMATS = ["mod", "xm", "s3m", "it"]
SEEDS = [1, 11, 7777]   # 7777 は音量の測定（tools/calibrate_levels.py）に使っていない seed
CLIP = 1.0          # float 出力の 1.0 = 0 dBFS。これ以上は整数 PCM・MP3 化で割れる
IDS = [g.id for g in engine.list_genres()]


@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("fmt", TRACKER_FORMATS)
@pytest.mark.parametrize("genre", IDS)
def test_real_playback_does_not_clip(genre, fmt, seed):
    pk = peak(engine.build(engine.get_genre(genre), seed, fmt).data, f".{fmt}")
    assert 0.05 < pk < CLIP, f"{genre} {fmt} seed {seed}: peak {pk:.3f}"
    if fmt in ("s3m", "it"):     # 音量の底上げ（DESIGN.md §7.9）: ヘッダの音量で目標の近くまで持ち上がる
        assert pk > 10 ** ((native_level.TARGET_PEAK_DB - 6) / 20), f"{genre} {fmt} seed {seed}: too quiet {pk:.3f}"


@pytest.mark.parametrize("genre,fmt", [("march", "mod"), ("pop", "mod"), ("pop", "s3m")])
def test_detects_clipping(genre, fmt):
    """検査が音割れを見逃さないこと: 全サンプルを振幅最大の矩形波・音量 64 にすると 0 dBFS を超える。"""
    g = engine.get_genre(genre)
    plan = resolve_plan(g, 1)
    score = compose(g, plan, 1, frozenset())
    rs = realize(g, score, plan, resolve(fmt, None, g, 1), level=False)
    square = bytes(0x7F if (i // 8) % 2 else 0x81 for i in range(4096))
    rs.samples = [dataclasses.replace(s, data=square, volume=64, loop=(0, len(square) // 2)) for s in rs.samples]
    assert peak(native.serialize(rs), f".{fmt}") > CLIP


@pytest.mark.parametrize("fmt", ["mod", "xm"])
@pytest.mark.parametrize("genre,channels", [(g.id, n) for g in engine.list_genres() for n in g.mod_channels])
def test_every_arrangement_does_not_clip(genre, channels, fmt):
    """曲ごとに選べる編成（DESIGN.md §6.14）はどれも音割れしない（XM は同じ数を上限にして作る）。"""
    pk = peak(engine.build(engine.get_genre(genre), 3, fmt, channels=channels).data, f".{fmt}")
    assert 0.05 < pk < CLIP, f"{genre} {channels}ch {fmt}: peak {pk:.3f}"
