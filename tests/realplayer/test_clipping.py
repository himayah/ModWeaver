"""全ジャンル・全トラッカー形式を実プレイヤー（libopenmpt）で再生し、音割れしない（最大振幅 < 0 dBFS）ことを検査する。

verify の V15（左右の同時合計音量 ≤ 120）はチャンネル音量の単純合計による目安で、実際の再生エンジンの
ミキシング（チャンネル数に応じたヘッドルーム、サンプル波形の振幅）を考えない。多チャンネルの全合奏では
割れなくても超えるため、``GenreProfile.allow_volume_sum_over`` を宣言したジャンルは V15 を検査しない。
その代わりに本テストが実測で音割れの有無を確かめる（宣言していないジャンルも含めて全ジャンル）。
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


def test_orchestral_opts_out_of_v15_only():
    """V15 を免除しているのは実測で割れないと確認した orchestral だけ（増やすときは本テストで確認してから）。"""
    assert [p.id for p in profiles.list_profiles() if p.allow_volume_sum_over] == ["orchestral"]


@pytest.mark.parametrize("genre,fmt", [("march", "mod"), ("orchestral", "xm")])
def test_detects_clipping(genre, fmt):
    """検査が音割れを見逃さないこと: 全サンプルを振幅最大の矩形波・音量 64 にすると 0 dBFS を超える。"""
    p = profiles.get_profile(genre)
    song, plan = engine.compose_song(p, 1)
    square = bytes(0x7F if (i // 8) % 2 else 0x81 for i in range(4096))
    song.samples = [dataclasses.replace(s, data=square, volume=64, loop=(0, len(square) // 2)) for s in song.samples]
    assert peak(engine.serialize(p, song, plan, fmt), f".{fmt}") > CLIP
