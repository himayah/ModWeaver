from __future__ import annotations

import struct

import pytest

from mod_weaver.core.model import Cell, ChannelRole, Pattern, SampleSpec, Song
from mod_weaver.core.verify import (
    ParseError, has_errors, parse_mod, parse_xm, verify, verify_xm,
)
from mod_weaver.core.formats import get_format
from mod_weaver.core.writer import serialize, serialize_xm


def good_song() -> Song:
    pat = Pattern()
    pat.put(0, 0, Cell(24, 1, 0xF, 100))
    pat.put(0, 1, Cell(12, 2))
    smp = [
        SampleSpec("One", bytes([0, 5, 10, 5, 0, 251, 246, 251] * 8), 50),
        SampleSpec("Loop", bytes([int(100 * ((i % 32) / 32 * 2 - 1)) & 0xFF for i in range(64)]), 40),
    ]
    return Song("T", smp, [pat], [0])


def codes(issues, level=None):
    return {i.code for i in issues if level is None or i.level == level}


def mutate(data: bytes, off: int, value: bytes) -> bytes:
    return data[:off] + value + data[off + len(value):]


def pat_off(row, ch, pattern=0):
    return 1084 + pattern * 1024 + (row * 4 + ch) * 4


def test_clean_file_has_no_errors():
    data = serialize(good_song())
    issues = verify(data)
    assert not has_errors(issues)
    assert get_format("mod").verify is verify


def test_parse_roundtrip_fields():
    pm = parse_mod(serialize(good_song()))
    assert pm.title.rstrip(b"\0") == b"T" and pm.song_length == 1 and pm.restart == 0x7F
    assert pm.patterns[0][0][0].effect == 0xF and pm.patterns[0][0][0].param == 100
    assert pm.samples[0].data[:3] == bytes([0, 5, 10])
    assert pm.pattern_count == 1


def test_too_short_file():
    with pytest.raises(ParseError):
        parse_mod(b"x" * 100)
    assert codes(verify(b"x" * 100), "ERROR") == {"V01"}


def test_v01_size_mismatch():
    data = serialize(good_song())
    assert "V01" in codes(verify(data + b"\0\0"), "ERROR")
    assert "V01" in codes(verify(data[:-2]), "ERROR")


def test_v02_magic_and_title():
    data = serialize(good_song())
    assert "V02" in codes(verify(mutate(data, 1080, b"M!K!")), "ERROR")
    assert "V02" in codes(verify(mutate(data, 0, b"\xff")), "ERROR")


def test_v03_song_length_restart_order():
    data = serialize(good_song())
    assert "V03" in codes(verify(mutate(data, 950, b"\x00")), "ERROR")
    assert "V03" in codes(verify(mutate(data, 950, b"\x81")), "ERROR")
    assert "V03" in codes(verify(mutate(data, 951, b"\x00")), "ERROR")
    assert "V03" in codes(verify(mutate(data, 952, b"\x01")), "ERROR")   # pattern 数超え（+V01）


def test_v04_sample_header():
    data = serialize(good_song())
    assert "V04" in codes(verify(mutate(data, 20 + 25, b"\x41")), "ERROR")                  # volume 65
    assert "V04" in codes(verify(mutate(data, 20 + 30 + 26, struct.pack(">HH", 30, 10))), "ERROR")  # loop 範囲外


def test_v05_invalid_period():
    data = serialize(good_song())
    assert "V05" in codes(verify(mutate(data, pat_off(1, 0), bytes([0x10, 0x01, 0x10, 0x00]))), "ERROR")


def test_v06_undefined_sample():
    data = serialize(good_song())
    assert "V06" in codes(verify(mutate(data, pat_off(1, 0), bytes([0x10 | 0x00, 214 & 0xFF, 0x50, 0]))), "ERROR")


def test_v07_note_without_sample():
    data = serialize(good_song())
    assert "V07" in codes(verify(mutate(data, pat_off(2, 0), bytes([0x00, 214, 0x00, 0x00]))), "ERROR")


def test_v08_effect_params():
    data = serialize(good_song())
    assert "V08" in codes(verify(mutate(data, pat_off(2, 2), bytes([0, 0, 0x0C, 65]))), "ERROR")
    assert "V08" in codes(verify(mutate(data, pat_off(2, 2), bytes([0, 0, 0x0F, 0]))), "ERROR")
    assert "V08" not in codes(verify(mutate(data, pat_off(2, 2), bytes([0, 0, 0x0C, 64]))))


def test_v09_channel_plan():
    plan = (ChannelRole("a", frozenset({1})), ChannelRole("b", frozenset({2})),
            ChannelRole("c", frozenset()), ChannelRole("d", frozenset()))
    data = serialize(good_song())
    assert not has_errors(verify(data, plan))
    bad = mutate(data, pat_off(3, 2), Cell(10, 1).serialize())
    assert "V09" in codes(verify(bad, plan), "ERROR")
    assert "V09" not in codes(verify(bad))            # plan 未指定なら検査しない


def test_v10_tempo_required_in_first_pattern():
    song = good_song()
    song.patterns[0] = Pattern()
    song.patterns[0].put(0, 1, Cell(12, 2))
    assert "V10" in codes(verify(serialize(song)), "ERROR")
    song.patterns[0].put(5, 0, Cell(None, 0, 0xF, 31))    # Speed 設定はテンポではない
    assert "V10" in codes(verify(serialize(song)), "ERROR")
    song.patterns[0].put(5, 0, Cell(None, 0, 0xF, 32))
    assert "V10" not in codes(verify(serialize(song)))


def test_v11_loop_boundary_step():
    song = good_song()
    song.samples[1] = SampleSpec("Loop", bytes(range(0, 32)) + bytes(32), 40, loop=(0, 16))
    issues = verify(serialize(song))
    assert "V11" in codes(issues, "WARN")                # なだらかな傾斜の末尾 → 先頭で 31 の段差
    song.samples[1] = SampleSpec("Loop", bytes(64), 40, loop=(0, 16))
    assert "V11" not in codes(verify(serialize(song)))   # 無音は誤検知しない（ガード）


def test_v12_too_many_patterns():
    pats = [Pattern() for _ in range(65)]
    pats[0] = good_song().patterns[0]
    song = Song("T", good_song().samples, pats, [64])
    assert "V12" in codes(verify(serialize(song)), "ERROR")


def test_v13_unused_sample_is_info():
    issues = verify(serialize(good_song()))
    assert "V13" not in codes(issues)
    song = good_song()
    song.patterns[0].replace(0, 1, Cell(None, 0))
    assert codes(verify(serialize(song)), "INFO") == {"V13"}


def test_v14_sample_without_note_or_effect():
    song = good_song()
    song.patterns[0].put(4, 1, Cell(None, 2))
    assert "V14" in codes(verify(serialize(song)), "WARN")


def test_v15_volume_sum_left_and_right():
    song = good_song()
    p = song.patterns[0]
    p.replace(0, 0, Cell(24, 1, 0xF, 100))
    p.replace(0, 3, Cell(24, 2, vol=64))            # 左: ch1(50) + ch4(64) = 114 → OK
    assert "V15" not in codes(verify(serialize(song)))
    p.replace(2, 0, Cell(24, 1, vol=64))
    p.replace(2, 3, Cell(24, 2, vol=64))            # 左 128
    p.replace(4, 1, Cell(24, 1, vol=64))
    p.replace(4, 2, Cell(24, 2, vol=64))            # 右 128
    issues = [i for i in verify(serialize(song)) if i.code == "V15"]
    assert len(issues) == 1 and issues[0].level == "WARN"
    assert "row 2" in issues[0].message


def test_v15_off_cell_reduces_sum_and_note_uses_sample_default():
    song = good_song()
    p = song.patterns[0]
    p.replace(0, 0, Cell(24, 1, vol=64))
    p.replace(0, 3, Cell(24, 2, vol=64))
    p.replace(1, 0, Cell(None, 0, vol=0))           # OFF → 合計が下がる
    p.replace(1, 3, Cell(None, 0, vol=0))
    p.replace(2, 0, Cell(24, 1))                    # 既定音量 50
    p.replace(2, 3, Cell(24, 2))                    # 既定音量 40
    hits = [i for i in verify(serialize(song)) if i.code == "V15"]
    assert len(hits) == 1 and "row 0" in hits[0].message


def test_v16_arpeggio_range():
    song = good_song()
    song.patterns[0].put(6, 2, Cell(28, 2, 0, 0x47))
    assert "V16" not in codes(verify(serialize(song)))
    song.patterns[0].replace(6, 2, Cell(29, 2, 0, 0x47))
    assert "V16" in codes(verify(serialize(song)), "ERROR")


def test_issue_messages_aggregate_locations():
    song = good_song()
    for r in range(10):
        song.patterns[0].put(r + 8, 0, Cell(29, 1, 0, 0x47))
    msg = next(i.message for i in verify(serialize(song)) if i.code == "V16")
    assert "[10件]" in msg and "(+7 more)" in msg


# ---------------- XM（EXT-6） ----------------

def good_xm_song(n_channels=6) -> Song:
    pat = Pattern(None, channels=n_channels)
    pat.put(0, 0, Cell(24, 1, 0xF, 100))
    pat.put(0, 1, Cell(12, 2))
    smp = [
        SampleSpec("One", bytes([0, 5, 10, 5, 0, 251, 246, 251] * 8), 50, pan=40),
        SampleSpec("Loop", bytes([int(100 * ((i % 32) / 32 * 2 - 1)) & 0xFF for i in range(64)]), 40, pan=220),
    ]
    return Song("XM T", smp, [pat], [0])


def test_xm_clean_file_has_no_errors():
    data = serialize_xm(good_xm_song())
    issues = verify_xm(data)
    assert not has_errors(issues)
    assert get_format("xm").verify is verify_xm


def test_xm_parse_error_on_short_file():
    with pytest.raises(ParseError):
        parse_xm(b"short")
    assert has_errors(verify_xm(b"short"))


def test_xm_v02_bad_magic():
    data = bytearray(serialize_xm(good_xm_song()))
    data[0:4] = b"XXXX"
    assert "V02" in codes(verify_xm(bytes(data)), "ERROR")


def test_xm_v06_undefined_instrument():
    song = good_xm_song()
    song.patterns[0].put(4, 0, Cell(20, 5))          # instrument 5 は未定義
    assert "V06" in codes(verify_xm(serialize_xm(song)), "ERROR")


def test_xm_v07_note_without_instrument():
    song = good_xm_song()
    song.patterns[0].replace(4, 0, Cell(20, 0))
    assert "V07" in codes(verify_xm(serialize_xm(song)), "ERROR")


def test_xm_v08_bad_effect_param():
    song = good_xm_song()
    song.patterns[0].replace(0, 0, Cell(None, 0, 0xF, 0))
    assert "V08" in codes(verify_xm(serialize_xm(song)), "ERROR")


def test_xm_v09_disallowed_instrument_on_channel():
    song = good_xm_song()
    plan = (ChannelRole("a", frozenset({2})),) + tuple(
        ChannelRole(f"c{i}", frozenset()) for i in range(1, 6)
    )
    song.patterns[0].put(6, 0, Cell(20, 2))          # ch0 は sample 2 を許可していない
    assert "V09" in codes(verify_xm(serialize_xm(song), plan), "ERROR")


def test_xm_v10_missing_tempo():
    song = good_xm_song()
    song.patterns[0].replace(0, 0, Cell(24, 1))      # テンポセルを消す
    assert "V10" in codes(verify_xm(serialize_xm(song)), "ERROR")


def test_xm_v13_unused_instrument():
    song = good_xm_song()
    song.patterns[0].replace(0, 1, Cell())           # instrument2（Loop）への唯一の参照を消す
    issues = verify_xm(serialize_xm(song))
    assert "V13" in codes(issues, "INFO")


def test_xm_v15_pan_weighted_volume_sum():
    song = good_xm_song()
    p = song.patterns[0]
    p.replace(0, 0, Cell(24, 1, vol=64))   # instrument1: pan=40 (左寄り)
    p.replace(0, 1, Cell(24, 2, vol=64))   # instrument2: pan=220 (右寄り)
    assert "V15" not in codes(verify_xm(serialize_xm(song)))
    for ch in range(6):                    # 全チャンネルが同じ row で鳴る → 片側に偏って上限超過
        p.replace(2, ch, Cell(24, 1 if ch % 2 == 0 else 2, vol=64))
    issues = verify_xm(serialize_xm(song))
    assert any(i.code == "V15" for i in issues)


def test_xm_v16_arpeggio_range():
    song = good_xm_song()
    song.patterns[0].put(6, 2, Cell(28, 2, 0, 0x47))
    assert "V16" not in codes(verify_xm(serialize_xm(song)))
    song.patterns[0].replace(6, 2, Cell(29, 2, 0, 0x47))
    assert "V16" in codes(verify_xm(serialize_xm(song)), "ERROR")


def test_xm_round_trips_through_real_genres():
    """全登録ジャンルの Song を XM へシリアライズし、parse_xm で自己無矛盾（バイト数一致・エラー無し）
    であることを確認する（実プレイヤーでの検証は tests/realplayer/。DESIGN.md §9.2）。"""
    from mod_weaver import engine
    from mod_weaver.profiles.registry import PROFILE_REGISTRY

    for name in sorted(PROFILE_REGISTRY):
        profile = PROFILE_REGISTRY[name]()
        song, _plan = engine.compose_song(profile, 1)
        data = serialize_xm(song)
        pm = parse_xm(data)
        assert pm.consumed == len(data), name
        assert not has_errors(verify_xm(data, profile.channel_plan)), name
