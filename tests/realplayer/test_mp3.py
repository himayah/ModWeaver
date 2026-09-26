"""--format mp3 を実際に ffmpeg で生成し、デコードして検査する（DESIGN.md §9.2）。"""
import math

import pytest

from mod_weaver import engine, profiles
from mod_weaver.core import render, timeline
from tests.realplayer import decode, requires_openmpt

pytestmark = requires_openmpt


@pytest.mark.parametrize("genre", ["nostalgic", "orchestral", "free-jazz"])
def test_mp3_decodes_with_expected_length_and_stereo(genre):
    p = profiles.get_profile(genre)
    song, plan = engine.compose_song(p, 123456)
    data = engine.serialize(p, song, plan, "mp3")
    assert data[:3] == b"ID3" or data[0] == 0xFF
    left, right = decode(data, ".mp3", demuxer=None, stereo=True)
    expected = timeline.build(song, plan.bpm).seconds
    assert abs(left.seconds - expected) <= 0.5, (left.seconds, expected)
    assert left.rms() > 300 and right.rms() > 300                      # 無音でない
    peak = max(max(abs(x) for x in left.samples), max(abs(x) for x in right.samples))
    clipped = sum(1 for x in left.samples if abs(x) >= 32767) / len(left.samples)
    assert peak > 1000 and clipped < 0.001


@pytest.mark.parametrize("genre", ["calm", "chiptune", "orchestral"])
def test_mp3_is_raised_to_the_target_loudness(genre):
    """2パスの音量調整（DESIGN.md §7.8）: 静かなジャンルも目標の平均音量の近くまで上がり、上限は超えない。"""
    p = profiles.get_profile(genre)
    song, plan = engine.compose_song(p, 1)
    left, right = decode(engine.serialize(p, song, plan, "mp3"), ".mp3", demuxer=None, stereo=True)
    rms = math.sqrt((left.rms() ** 2 + right.rms() ** 2) / 2) / 32768
    peak = max(max(abs(x) for x in left.samples), max(abs(x) for x in right.samples)) / 32768
    assert 20 * math.log10(rms) > render.TARGET_MEAN_DB - 4
    assert 20 * math.log10(peak) < 0
