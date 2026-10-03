"""XM を実プレイヤー（libopenmpt）で再生し、同じ曲の MOD 再生と長さ・音量包絡が一致することを検査する。

XM note 番号の規約の回帰テスト。以前は t+1 と書いていて 3 オクターブ低く鳴っていたが、writer と parse_xm が同じ誤りを
共有していたため自己ラウンドトリップ検査は緑のままだった。音高そのものは I4（test_f4_formats.py）が楽器ごとに測る。
XM は 16-bit・高レートのサンプルなので、曲全体の零交差の平均は MOD と違う（長さと音量包絡で見る）。
"""
import pytest

from mod_weaver import engine
from tests.realplayer import correlation, decode, requires_openmpt

pytestmark = requires_openmpt


@pytest.mark.parametrize("genre", ["nostalgic", "march", "maqam"])
def test_xm_sounds_at_same_pitch_and_length_as_mod(genre):
    g = engine.get_genre(genre)
    mod = decode(engine.build(g, 123456, "mod").data, ".mod")
    xm = decode(engine.build(g, 123456, "xm").data, ".xm")
    assert xm.stderr == ""
    assert abs(xm.seconds - mod.seconds) <= 0.01 * mod.seconds + 0.1
    assert correlation(mod.envelope(), xm.envelope()) > 0.8
