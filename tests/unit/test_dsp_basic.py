from __future__ import annotations

import pytest

from mod_weaver.core import dsp


def test_sample_rate_values():
    assert dsp.sample_rate(24) == pytest.approx(8287.14, abs=0.01)
    assert dsp.sample_rate(35) == pytest.approx(15694.2, abs=0.1)
    assert dsp.sample_rate(12) == pytest.approx(4143.6, abs=0.1)


def test_clamp_rounds_half_to_even_and_pads_to_even_length():
    xs = [-1000, -128.5, -128, -0.5, 0, 0.5, 1.5, 126.5, 127, 127.4, 500, 2.5, 3.5]
    assert [dsp.clamp(x) for x in xs] == [-128, -128, -128, 0, 0, 0, 2, 126, 127, 127, 127, 2, 4]
    assert [dsp.pad_even(b) for b in [b"", b"a", b"ab", b"abc"]] == [b"", b"a\x00", b"ab", b"abc\x00"]


def test_to_pcm():
    assert dsp.to_pcm([0.0, 1.0, -1.0]) == bytes([0, 127, 129, 0])  # 奇数長は 0 で偶数化
    assert dsp.to_pcm([2.0, -2.0]) == bytes([127, 128])
    assert len(dsp.to_pcm([0.1] * 5)) % 2 == 0
