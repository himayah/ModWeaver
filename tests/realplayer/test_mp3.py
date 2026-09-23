"""--format mp3 を実際に ffmpeg で生成し、デコードして検査する（FORMAT_TEMPO_DESIGN §5.2）。"""
import pytest

from mod_weaver import engine, profiles
from mod_weaver.core import timeline
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
