"""MP3 の音量調整の計算（DESIGN.md §7.8、core/render.py）。ffmpeg は使わない。"""
import pytest

from mod_weaver.core import render
from mod_weaver.errors import ExternalToolError


def test_loudness_gain_reaches_the_target_mean():
    assert render.loudness_gain(-24.0, -12.0) == pytest.approx(10.0)


def test_loudness_gain_limits_how_much_the_limiter_cuts():
    assert render.loudness_gain(-24.0, -4.0) == pytest.approx(render.LIMIT_DB + render.MAX_LIMITING_DB + 4.0)


def test_loudness_gain_never_turns_down():
    assert render.loudness_gain(-10.0, -0.5) == 0.0


def test_parse_volumedetect():
    err = "[Parsed_volumedetect_0 @ 0x1] mean_volume: -23.4 dB\n[Parsed_volumedetect_0 @ 0x1] max_volume: -6.5 dB\n"
    assert render._parse_volumedetect(err) == (-23.4, -6.5)
    silent = "mean_volume: -inf dB\nmax_volume: -inf dB\n"
    assert render.loudness_gain(*render._parse_volumedetect(silent)) == 0.0
    with pytest.raises(ExternalToolError):
        render._parse_volumedetect("nothing")
