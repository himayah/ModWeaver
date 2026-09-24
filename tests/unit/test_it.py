import struct

import pytest

from mod_weaver import engine, profiles
from mod_weaver.core import it
from mod_weaver.core.formats import WriteOptions
from mod_weaver.core.model import Cell, Pattern, SampleSpec, Song
from mod_weaver.core.verify import has_errors
from mod_weaver.errors import PlanError


def song(n_channels=4):
    pat = Pattern(None, channels=n_channels)
    pat.put(0, 0, Cell(12, 1, 0xF, 125))
    pat.put(1, 1, Cell(0, 2, vol=40))
    pat.put(2, 2, Cell(35, 1, 0x4, 0x46))
    samples = [SampleSpec("One", bytes(range(0, 64)), 50),
               SampleSpec("Two", bytes(64), 33, loop=(4, 20), finetune=3, pan=30)]
    return Song("IT Test", samples, [pat], [0, 0])


def opts(n=4, bpm=125):
    return WriteOptions(channel_pans=tuple(64 if c % 4 in (0, 3) else 192 for c in range(n)), initial_bpm=bpm)


def test_header_layout():
    data = it.serialize_it(song(), opts(bpm=99))
    assert data[:4] == b"IMPM" and data[4:11] == b"IT Test"
    ord_num, ins_num, smp_num, pat_num, cwt, cmwt, flags = struct.unpack("<7H", data[0x20:0x2E])
    assert (ord_num, ins_num, smp_num, pat_num) == (3, 0, 2, 1)            # order + 終端 255
    assert flags == it.FLAG_STEREO | it.FLAG_OLD_EFFECTS                   # サンプルモード・Amiga slides
    assert (data[0x32], data[0x33]) == (6, 99)
    assert list(data[0x40:0x44]) == [16, 48, 48, 16] and data[0x44] & it.CHANNEL_DISABLED
    assert data[0xC0:0xC3] == bytes([0, 0, 255])


def test_round_trip():
    data = it.serialize_it(song(), opts())
    pm = it.parse_it(data)
    assert pm.channels == 4
    assert pm.patterns[0][0][0] == it.ParsedITCell(60, 1, -1, ord("T") - 64, 125)
    assert pm.patterns[0][1][1] == it.ParsedITCell(48, 2, 40, 0, 0)
    assert pm.patterns[0][2][2] == it.ParsedITCell(83, 1, -1, ord("H") - 64, 0x46)
    one, two = pm.samples
    assert one.data == bytes(range(0, 64)) and one.cvt & it.CVT_SIGNED and not one.dfp & it.DFP_ENABLED
    assert two.flags & it.SAMPLE_FLAG_LOOP and (two.loop_begin, two.loop_end) == (8, 48)
    assert two.dfp == it.DFP_ENABLED | it.pan64(30) and two.c5speed == round(8363 * 2 ** (3 / 96))
    assert not has_errors(it.verify_it(data))


def test_verify_detects_problems():
    s = song()
    s.patterns[0].replace(3, 0, Cell(12, 9))
    assert "V06" in [i.code for i in it.verify_it(it.serialize_it(s, opts()))]
    assert [i.code for i in it.verify_it(b"short")] == ["V01"]


def test_too_many_channels_rejected():
    with pytest.raises(PlanError):
        it.serialize_it(song(65), opts(65))


@pytest.mark.parametrize("genre", [c.id for c in profiles.list_profiles()])
def test_all_genres_serialize_cleanly(genre):
    p = profiles.get_profile(genre)
    song_, plan = engine.compose_song(p, 1)
    assert not has_errors(it.verify_it(engine.serialize(p, song_, plan, "it"), engine.effective_channel_plan(p, plan)))
