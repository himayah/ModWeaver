"""各ジャンルが「表示している BPM」で実際に鳴ることを実プレイヤー（libopenmpt）の再生時間で検査する
（FORMAT_TEMPO_DESIGN §1.3。swing-jazz が表示の2倍の速さで鳴っていた不具合の回帰テスト）。

期待再生時間 = 再生される総 row 数 / (1拍の row 数) × 60 / BPM。
trap は 32分格子（1拍=8row）だが、trap の慣習的な BPM 表記（ハーフタイムの倍で数える）に合わせて
「16分音符＝4row を1拍」と数える＝表示 150 は「150 BPM の trap」として鳴る。
free-jazz はテンポカーブで BPM が推移するため対象外。
"""
import pytest

from mod_weaver import profiles
from mod_weaver.core import writer
from mod_weaver.engine import compose_song
from tests.realplayer import decode, requires_openmpt

pytestmark = requires_openmpt

ROWS_PER_BEAT = {"swing-jazz": 2}          # 既定 4（16分音符格子）


def _played_rows(profile, plan) -> int:
    per_pattern = [sum((s.rows or profile.rows_per_measure) * s.measures for s in pp.slots) for pp in plan.patterns]
    return sum(per_pattern[i] for i in plan.order)


@pytest.mark.parametrize("genre", [p.id for p in profiles.list_profiles() if p.id != "free-jazz"])
def test_genre_plays_at_its_displayed_bpm(genre):
    profile = profiles.get_profile(genre)
    song, plan = compose_song(profile, 123456)
    beats = _played_rows(profile, plan) / ROWS_PER_BEAT.get(genre, 4)
    expected = beats * 60.0 / plan.bpm
    actual = decode(writer.serialize_xm(song), ".xm").seconds
    assert abs(actual - expected) <= 0.02 * expected + 0.3, (plan.bpm, expected, actual)


@pytest.mark.parametrize("genre", [p.id for p in profiles.list_profiles()])
def test_timeline_length_matches_real_player(genre):
    """core/timeline.py（MIDI の時間軸の根拠）の曲長が libopenmpt の再生時間と一致する
    （libopenmpt は最後の row の後に僅かな余韻を含むので +0.2 秒まで許容）。"""
    from mod_weaver.core import timeline

    profile = profiles.get_profile(genre)
    song, plan = compose_song(profile, 123456)
    actual = decode(writer.serialize_xm(song, initial_bpm=plan.bpm), ".xm").seconds
    assert 0 <= actual - timeline.build(song, plan.bpm).seconds <= 0.2
