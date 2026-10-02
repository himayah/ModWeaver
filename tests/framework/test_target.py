"""``framework/target.py``（FRAMEWORK_REDESIGN.md §4）の検査。"""
from __future__ import annotations

import pytest

from mod_weaver.errors import ChannelCountError, PlanError
from mod_weaver.framework import target


class _FakeGenre:
    id = "fake"
    mod_channels = {4: 1, 6: 2, 8: 1}
    channel_cap = None


def test_mod_budget_honors_explicit_channels_request():
    t = target.resolve("mod", 6, _FakeGenre(), seed=1)
    assert t.budget == 6
    assert t.sample.bits == 8
    assert t.note_range == (0, 35)


def test_mod_budget_rejects_unsupported_channels():
    with pytest.raises(ChannelCountError):
        target.resolve("mod", 5, _FakeGenre(), seed=1)


def test_mod_budget_is_deterministic_per_seed_without_request():
    a = target.resolve("mod", None, _FakeGenre(), seed=42)
    b = target.resolve("mod", None, _FakeGenre(), seed=42)
    assert a.budget == b.budget
    assert a.budget in (4, 6, 8)


def test_xm_defaults_to_full_budget_and_16bit():
    t = target.resolve("xm", None, _FakeGenre(), seed=1)
    assert t.budget == 32
    assert t.sample.bits == 16
    assert t.note_range == (0, 95)
    assert "tremolo" in t.features


def test_it_budget_respects_channel_cap():
    class Capped(_FakeGenre):
        channel_cap = 10
    t = target.resolve("it", None, Capped(), seed=1)
    assert t.budget == 10


def test_channels_request_out_of_range_for_tracker_format_raises():
    with pytest.raises(ChannelCountError):
        target.resolve("s3m", 99, _FakeGenre(), seed=1)


def test_midi_rejects_channels_request():
    with pytest.raises(ChannelCountError):
        target.resolve("midi", 8, _FakeGenre(), seed=1)


def test_midi_budget_is_16_and_has_no_sample_caps():
    t = target.resolve("midi", None, _FakeGenre(), seed=1)
    assert t.budget == 16
    assert t.sample is None


def test_mp3_mirrors_it_but_keeps_its_own_format_name():
    it_t = target.resolve("it", None, _FakeGenre(), seed=1)
    mp3_t = target.resolve("mp3", None, _FakeGenre(), seed=1)
    assert mp3_t.format == "mp3"
    assert mp3_t.budget == it_t.budget
    assert mp3_t.sample == it_t.sample


def test_unknown_format_raises():
    with pytest.raises(PlanError):
        target.resolve("wav", None, _FakeGenre(), seed=1)
