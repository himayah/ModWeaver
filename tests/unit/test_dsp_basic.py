from __future__ import annotations

import pytest

from mod_weaver.core import dsp
from tests.conftest import load_reference


def test_sample_rate_values():
    assert dsp.sample_rate(24) == pytest.approx(8287.14, abs=0.01)
    assert dsp.sample_rate(35) == pytest.approx(15694.2, abs=0.1)
    assert dsp.sample_rate(12) == pytest.approx(4143.6, abs=0.1)


def test_sample_rate_equals_legacy_SR():
    assert dsp.sample_rate(24) == load_reference().SR  # bit-exact（D11 の前提）


def test_clamp_and_pad_match_legacy():
    ref = load_reference()
    for x in [-1000, -128.5, -128, -0.5, 0, 0.5, 1.5, 126.5, 127, 127.4, 500, 2.5, 3.5]:
        assert dsp.clamp(x) == ref.clamp(x)
    for b in [b"", b"a", b"ab", b"abc"]:
        assert dsp.pad_even(b) == ref.pad_even(b)


def test_to_pcm():
    assert dsp.to_pcm([0.0, 1.0, -1.0]) == bytes([0, 127, 129, 0])  # 奇数長は 0 で偶数化
    assert dsp.to_pcm([2.0, -2.0]) == bytes([127, 128])
    assert len(dsp.to_pcm([0.1] * 5)) % 2 == 0
