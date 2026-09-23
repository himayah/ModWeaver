"""XM を実プレイヤー（libopenmpt）で再生し、同じ Song の MOD 再生と音高・長さが一致することを検査する。

XM note 番号の規約（t=0 → C-3＝note 37）の回帰テスト。以前は t+1 と書いていて 3 オクターブ低く鳴っていたが、
writer と parse_xm が同じ誤りを共有していたため自己ラウンドトリップ検査は緑のままだった。
"""
import pytest

from mod_weaver import profiles
from mod_weaver.core import writer
from mod_weaver.engine import build_song
from tests.realplayer import correlation, decode, requires_openmpt

pytestmark = requires_openmpt


@pytest.mark.parametrize("genre", ["nostalgic", "march", "maqam"])
def test_xm_sounds_at_same_pitch_and_length_as_mod(genre):
    song = build_song(profiles.get_profile(genre), 123456)
    mod = decode(writer.serialize(song), ".mod")
    xm = decode(writer.serialize_xm(song), ".xm")
    assert xm.stderr == ""
    assert abs(xm.seconds - mod.seconds) <= 0.01 * mod.seconds + 0.1
    f_mod, f_xm = mod.mean_freq(0, 20), xm.mean_freq(0, 20)
    assert abs(f_xm - f_mod) <= 0.05 * f_mod, (f_mod, f_xm)
    assert correlation(mod.envelope(), xm.envelope()) > 0.8
