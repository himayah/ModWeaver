"""全ジャンル・全トラッカー形式を実プレイヤー（libopenmpt）で再生し、音割れしない（最大振幅 < 0 dBFS）ことを検査する。

verify の V15（左右の同時合計音量 ≤ 120）はチャンネル音量の単純合計による目安で、実際の再生エンジンの
ミキシング（チャンネル数に応じたヘッドルーム、サンプル波形の振幅）を考えない。多チャンネルでは割れなくても
超えるため V15 は 4ch の曲だけを検査する。その代わりに本テストが全ジャンルの音割れを実測で確かめる。
"""
import dataclasses

import pytest

from mod_weaver import engine, profiles
from tests.realplayer import peak, requires_openmpt

pytestmark = requires_openmpt

TRACKER_FORMATS = ["mod", "xm", "s3m", "it"]
SEEDS = [1, 11]
CLIP = 1.0          # float 出力の 1.0 = 0 dBFS。これ以上は整数 PCM・MP3 化で割れる


@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("fmt", TRACKER_FORMATS)
@pytest.mark.parametrize("genre", [p.id for p in profiles.list_profiles()])
def test_real_playback_does_not_clip(genre, fmt, seed):
    p = profiles.get_profile(genre)
    song, plan = engine.compose_song(p, seed)
    pk = peak(engine.serialize(p, song, plan, fmt), f".{fmt}")
    assert 0.05 < pk < CLIP, f"{genre} {fmt} seed {seed}: peak {pk:.3f}"


def test_multichannel_genres_generate_without_v15_warnings(tmp_path):
    """多チャンネル（orchestral の全合奏など）では V15 を出さない（4ch の曲だけが対象）。"""
    for p in profiles.list_profiles():
        for n in engine.channel_choices(p):
            if n != 4:
                res = engine.generate(profiles.get_profile(p.id), 11, tmp_path / f"{p.id}_{n}.mod", channels=n)
                assert not any(i.code == "V15" for i in res.issues), (p.id, n)


@pytest.mark.parametrize("genre,fmt", [("march", "mod"), ("orchestral", "xm")])
def test_detects_clipping(genre, fmt):
    """検査が音割れを見逃さないこと: 全サンプルを振幅最大の矩形波・音量 64 にすると 0 dBFS を超える。"""
    p = profiles.get_profile(genre)
    song, plan = engine.compose_song(p, 1)
    square = bytes(0x7F if (i // 8) % 2 else 0x81 for i in range(4096))
    song.samples = [dataclasses.replace(s, data=square, volume=64, loop=(0, len(square) // 2)) for s in song.samples]
    assert peak(engine.serialize(p, song, plan, fmt), f".{fmt}") > CLIP


@pytest.mark.parametrize("fmt", ["mod", "xm"])
@pytest.mark.parametrize("genre,channels", [
    (p.id, n) for p in profiles.list_profiles() if p.channel_choices for n in p.channel_choices])
def test_every_arrangement_does_not_clip(genre, channels, fmt):
    """曲ごとに選べる編成（DESIGN.md §6.14）はどれも音割れしない。"""
    p = profiles.get_profile(genre)
    song, plan = engine.compose_song(p, 3, channels=channels)
    pk = peak(engine.serialize(p, song, plan, fmt), f".{fmt}")
    assert 0.05 < pk < CLIP, f"{genre} {channels}ch {fmt}: peak {pk:.3f}"
