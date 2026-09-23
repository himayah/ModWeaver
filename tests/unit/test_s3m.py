import struct

import pytest

from mod_weaver import engine, profiles
from mod_weaver.core import s3m
from mod_weaver.core.formats import WriteOptions
from mod_weaver.core.model import Cell, Pattern, SampleSpec, Song
from mod_weaver.core.verify import has_errors
from mod_weaver.errors import PlanError


def song(n_channels=4):
    pat = Pattern(None, channels=n_channels)
    pat.put(0, 0, Cell(12, 1, 0xF, 125))
    pat.put(1, 1, Cell(0, 2, vol=40))
    pat.put(2, 2, Cell(35, 1, 0xE, 0x93))
    samples = [SampleSpec("One", bytes(range(0, 64)), 50), SampleSpec("Two", bytes(64), 33, loop=(4, 20), finetune=-8)]
    return Song("S3M Test", samples, [pat], [0])


def opts(n=4, bpm=125):
    return WriteOptions(channel_pans=tuple(64 if c % 4 in (0, 3) else 192 for c in range(n)), initial_bpm=bpm)


def test_note_byte_and_c2spd():
    assert s3m.note_byte(0) == 0x30 and s3m.note_byte(12) == 0x40 and s3m.note_byte(35) == 0x5B
    assert s3m.c2spd(0) == 8363 and s3m.c2spd(-8) == round(8363 * 2 ** (-1 / 12))


def test_header_layout():
    data = s3m.serialize_s3m(song(), opts(bpm=111))
    assert data[:8] == b"S3M Test" and data[28:30] == bytes([0x1A, 16]) and data[44:48] == b"SCRM"
    ord_num, ins_num, pat_num, flags, cwt, ffi = struct.unpack("<6H", data[32:44])
    assert (ord_num, ins_num, pat_num, cwt, ffi) == (2, 2, 1, 0x1320, 2)     # order は偶数個に揃える
    assert data[49:51] == bytes([6, 111]) and data[53] == 0xFC
    assert data[64:68] == bytes([0, 8, 9, 1]) and set(data[68:96]) == {255}   # L R R L


def test_round_trip_cells_and_samples():
    data = s3m.serialize_s3m(song(), opts())
    pm = s3m.parse_s3m(data)
    assert pm.orders == [0, 255] and pm.channels == 4
    assert pm.patterns[0][0][0] == s3m.ParsedS3MCell(0x40, 1, -1, ord("T") - 64, 125)
    assert pm.patterns[0][1][1] == s3m.ParsedS3MCell(0x30, 2, 40, 0, 0)
    assert pm.patterns[0][2][2] == s3m.ParsedS3MCell(0x5B, 1, -1, ord("Q") - 64, 0x03)
    one, two = pm.samples
    assert one.data == bytes(b ^ 0x80 for b in range(0, 64))                 # unsigned
    assert (two.flags & 1, two.loop_start, two.loop_end, two.volume) == (1, 8, 48, 33)
    assert all(p % 16 == 0 for p in (0,))                                     # sanity
    assert not has_errors(s3m.verify_s3m(data))


def test_verify_detects_problems():
    good = song()
    good.patterns[0].replace(3, 0, Cell(12, 9))          # 未定義 instrument
    assert "V06" in [i.code for i in s3m.verify_s3m(s3m.serialize_s3m(good, opts()))]
    assert [i.code for i in s3m.verify_s3m(b"short")] == ["V01"]


def test_too_many_channels_rejected():
    with pytest.raises(PlanError):
        s3m.serialize_s3m(song(17), opts(17))


@pytest.mark.parametrize("genre", [c.id for c in profiles.list_profiles()])
def test_all_genres_serialize_cleanly(genre):
    p = profiles.get_profile(genre)
    song_, plan = engine.compose_song(p, 1)
    data = engine.serialize(p, song_, plan, "s3m")
    assert not has_errors(s3m.verify_s3m(data, p.channel_plan))
