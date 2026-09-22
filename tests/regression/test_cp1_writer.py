"""CP1: writer / Cell / pitch / verify の等価性（設計書 §11.4）。

旧実装の出力 mod（20 seed）を独立パーサ ``parse_mod`` で復元し、
新 ``serialize`` で再構築したバイト列が元と完全一致することを確認する。
"""
from __future__ import annotations

import pytest

from mod_weaver.core import pitch
from mod_weaver.core.model import Cell, Pattern, SampleSpec, Song
from mod_weaver.core.verify import has_errors, parse_mod, verify
from mod_weaver.core.writer import serialize
from tests.conftest import REGRESSION_SEEDS, legacy_mod_bytes


def song_from_parsed(data: bytes) -> Song:
    pm = parse_mod(data)
    samples = []
    for s in pm.samples:
        if s.length_words == 0:
            continue
        loop = (s.loop_start, s.loop_length) if s.loop_length > 1 else None
        samples.append(SampleSpec(s.name.rstrip(b"\0").decode("ascii"), s.data, s.volume, loop=loop))
    patterns = []
    for rows in pm.patterns:
        pat = Pattern()
        for r, row in enumerate(rows):
            for c, pc in enumerate(row):
                note = pitch.period_to_index(pc.period) if pc.period else None
                pat.put(r, c, Cell(note, pc.sample, pc.effect, pc.param))
        patterns.append(pat)
    title = pm.title.rstrip(b"\0").decode("ascii")
    return Song(title, samples, patterns, pm.order[:pm.song_length])


@pytest.mark.parametrize("seed", REGRESSION_SEEDS)
def test_serialize_reproduces_legacy_bytes(seed):
    legacy = legacy_mod_bytes(seed)
    assert serialize(song_from_parsed(legacy)) == legacy


@pytest.mark.parametrize("seed", REGRESSION_SEEDS)
def test_verify_accepts_legacy_output(seed):
    issues = verify(legacy_mod_bytes(seed))
    assert not has_errors(issues), issues
    # 旧実装の MellowFlute は未使用（既知: V13 INFO のみ）
    assert {i.code for i in issues} <= {"V13"}
