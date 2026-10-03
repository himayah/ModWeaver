from __future__ import annotations

import os
import struct

import pytest

from mod_weaver.core.model import Cell, Pattern, SampleSpec, Song
from mod_weaver.core.writer import mod_magic, serialize, write_file
from mod_weaver.errors import OutputError, PlanError, SampleConstraintError


def make_song(**kw) -> Song:
    pat = Pattern()
    pat.put(0, 0, Cell(24, 1, 0xF, 100))
    pat.put(1, 1, Cell(12, 2, vol=40))
    samples = [
        SampleSpec("One", bytes(range(0, 64)), 50),
        SampleSpec("Two", bytes(range(0, 128, 2)), 33, loop=(4, 20)),
    ]
    base = dict(title="Test Song", samples=samples, patterns=[pat, Pattern()], order=[0, 1, 0])
    base.update(kw)
    return Song(**base)


def test_header_layout():
    data = serialize(make_song())
    assert data[0:20] == b"Test Song".ljust(20, b"\x00")
    assert data[20:42] == b"One".ljust(22, b"\x00")
    assert struct.unpack(">H", data[42:44])[0] == 32           # length words
    assert data[44] == 0 and data[45] == 50                    # finetune, volume
    assert struct.unpack(">HH", data[46:50]) == (0, 1)         # 既定ループ
    assert struct.unpack(">HH", data[50 + 22 + 4:50 + 22 + 8]) == (4, 20)
    assert data[20 + 30 * 2:20 + 30 * 31] == b"\x00" * (30 * 29)     # 未使用 29 サンプルは 0
    assert data[950] == 3 and data[951] == 0x7F
    assert list(data[952:955]) == [0, 1, 0] and data[955:1080] == b"\x00" * 125
    assert data[1080:1084] == b"M.K."


def test_size_and_pattern_count_from_max_order():
    song = make_song(patterns=[Pattern(), Pattern(), Pattern()], order=[0, 1])
    data = serialize(song)
    assert len(data) == 1084 + 2 * 1024 + 64 + 64        # 未使用の pattern 2 は書かない
    assert data.endswith(song.samples[1].data)


def test_finetune_written_as_nibble():
    song = make_song()
    song.samples[0].finetune = -1
    assert serialize(song)[44] == 0x0F


@pytest.mark.parametrize("kw", [
    dict(title="x" * 21), dict(title="日本"), dict(order=[]), dict(order=[0] * 129),
    dict(order=[5]), dict(order=[-1]),
])
def test_plan_errors(kw):
    with pytest.raises(PlanError):
        serialize(make_song(**kw))


def test_too_many_samples():
    s = SampleSpec("a", bytes(2), 10)
    with pytest.raises(PlanError):
        serialize(make_song(samples=[s] * 32))


def test_sample_constraint_propagates():
    bad = SampleSpec("a", bytes(3), 10)
    with pytest.raises(SampleConstraintError):
        serialize(make_song(samples=[bad]))


@pytest.mark.parametrize("n, magic", [(4, b"M.K."), (1, b"1CHN"), (6, b"6CHN"), (8, b"8CHN"), (10, b"10CH"), (32, b"32CH")])
def test_mod_magic_for_channel_counts(n, magic):
    assert mod_magic(n) == magic


def test_mod_multichannel_round_trips_via_parse_mod():
    from mod_weaver.core.verify import parse_mod, verify

    pat = Pattern(channels=8)
    pat.put(0, 7, Cell(12, 1, 0xF, 125))
    song = Song("Eight", [SampleSpec("S", bytes(64), 40)], [pat], [0])
    data = serialize(song)
    assert data[1080:1084] == b"8CHN" and len(data) == 1084 + 64 * 8 * 4 + 64
    pm = parse_mod(data)
    assert pm.channels == 8 and pm.patterns[0][0][7].sample == 1
    assert not [i for i in verify(data) if i.level == "ERROR"]


# ---------------- XM（EXT-6） ----------------


def test_write_file_creates_and_overwrites_existing(tmp_path):
    p = tmp_path / "a.mod"
    write_file(p, b"first")
    write_file(p, b"second")                       # 既存ファイルの上書き（Windows でも成功する経路）
    assert p.read_bytes() == b"second"
    assert [f.name for f in tmp_path.iterdir()] == ["a.mod"]     # 一時ファイルが残らない


def test_write_file_failure_leaves_no_temp(tmp_path):
    with pytest.raises(OutputError):
        write_file(tmp_path / "no_such_dir" / "a.mod", b"x")
    d = tmp_path / "dest.mod"
    d.mkdir()                                       # 置換先がディレクトリ → os.replace 失敗
    with pytest.raises(OutputError):
        write_file(d, b"x")
    assert [f.name for f in tmp_path.iterdir()] == ["dest.mod"]


def test_write_file_default_permissions(tmp_path):
    p = tmp_path / "m.mod"
    write_file(p, b"x")
    umask = os.umask(0)
    os.umask(umask)
    assert (p.stat().st_mode & 0o777) == (0o666 & ~umask)
