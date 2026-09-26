"""出力音量の底上げ（DESIGN.md §7.9、core/level.py）。"""
import dataclasses

import pytest

from mod_weaver import engine, profiles
from mod_weaver.core import it, level, s3m, verify
from mod_weaver.core.formats import WriteOptions
from mod_weaver.core.model import Cell, Pattern, SampleSpec, Song
from mod_weaver.profiles.levels import PEAK_DB

PANS = (64, 192, 192, 64)


def song(vols=(32, 16), sample_volume=20, channels=2):
    pat = Pattern(None, channels=channels)
    for ch, v in enumerate(vols):
        pat.put(0, ch, Cell(12, 1, vol=v))
    pat.put(1, 0, Cell(12, 1))                         # 音量なし: サンプル既定音量で鳴る
    pat.put(2, 1, Cell(None, 0, vol=0))                # 消音は 0 のまま
    return Song("Level", [SampleSpec("One", bytes(64), sample_volume)], [pat], [0])


def vols(s):
    pat = s.patterns[0]
    return [pat.get(r, ch).vol for r in range(3) for ch in range(pat.channels)]


def test_volume_gain_scales_every_volume_and_keeps_the_original():
    s = song()
    louder = level.apply_volume_gain(s, 2.0)
    assert vols(louder) == [64, 32, None, None, None, 0]
    assert louder.samples[0].volume == 40
    assert vols(s) == [32, 16, None, None, None, 0] and s.samples[0].volume == 20


def test_volume_room_stops_at_the_loudest_volume():
    assert level.volume_room(song((32, 16), 20)) == 2.0
    assert level.volume_room(song((16, 16), 40)) == 64 / 40


def test_volume_room_keeps_v15_for_4ch_songs():
    s = song((40, 40, 40, 40), 1, channels=4)          # 左 = ch1+ch4 = 80、右 = ch2+ch3 = 80
    assert level.volume_room(s) == 64 / 40             # sides を渡さなければ見ない
    assert level.volume_room(s, level.mod_sides) == 120 / 80
    xm = level.volume_room(s, level.xm_sides(s, PANS))  # Px に丸めたパン（68／204）で加重すると重みの和が 1 を超える
    assert xm == pytest.approx(120 / (80 * (68 + 204) / 255))


def test_plan_level_uses_header_volume_first_for_s3m_and_it():
    s = song()
    peaks = {"mod": -8.0, "xm": -8.0, "s3m": -8.0, "it": -8.0}   # −2 dBFS まで 6 dB（約 2 倍）
    for fmt in ("s3m", "it"):
        lv = level.plan_level(s, fmt, peaks)
        assert lv.volume_gain == 1.0 and lv.header_volume == 95
    lv = level.plan_level(s, "mod", peaks)
    assert lv.header_volume == level.HEADER_VOLUME and lv.volume_gain == pytest.approx(10 ** 0.3)
    loud = {"it": -20.0}                               # ヘッダだけでは足りない分は音量の値で
    lv = level.plan_level(s, "it", loud)
    assert lv.header_volume == 128 and lv.volume_gain == 2.0


def test_plan_level_never_turns_down_and_skips_unmeasured_genres():
    s = song()
    assert level.plan_level(s, "xm", {"xm": -1.0}) == level.Level()
    assert level.plan_level(s, "xm", None) == level.Level()
    assert level.plan_level(s, "mp3", {"xm": -8.0}).volume_gain > 1        # mp3 は XM を経由する


def test_midi_is_raised_until_the_loudest_note_is_velocity_127():
    assert level.plan_level(song(), "midi", None) == level.Level(2.0)


def test_header_volume_is_written():
    s = song()
    opts = WriteOptions(channel_pans=PANS[:2], mix_volume=100)
    assert s3m.serialize_s3m(s, opts)[51] == 0x80 | 100
    assert it.serialize_it(s, opts)[0x31] == 100


def test_every_genre_has_measured_peaks():
    assert set(PEAK_DB) == {p.id for p in profiles.list_profiles()}
    assert all(set(v) == {"mod", "xm", "s3m", "it"} for v in PEAK_DB.values())


@pytest.mark.parametrize("genre", ["calm", "orchestral", "nostalgic"])
def test_leveling_changes_only_volumes(genre):
    """同じ seed の曲は、音量の値以外（音符・効果・サンプル波形）は変わらない。"""
    p = profiles.get_profile(genre)
    s, plan = engine.compose_song(p, 5)
    louder, _ = engine.leveled(p, s, plan, "mod")
    strip = lambda c: dataclasses.replace(c, vol=None)  # noqa: E731
    for a, b in zip(s.patterns, louder.patterns):
        assert a.mapped(strip).serialize() == b.mapped(strip).serialize()
    assert [x.data for x in s.samples] == [x.data for x in louder.samples]


def test_generated_4ch_songs_stay_within_v15():
    for g in ("nostalgic", "future-bass", "free-jazz"):
        p = profiles.get_profile(g)
        s, plan = engine.compose_song(p, 1)
        for fmt, check in (("mod", verify.verify), ("xm", verify.verify_xm)):
            assert not [i for i in check(engine.serialize(p, s, plan, fmt)) if i.code == "V15"], (g, fmt)
