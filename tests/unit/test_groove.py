from __future__ import annotations

import pytest

from mod_weaver.core import groove
from mod_weaver.core.model import Cell, Pattern
from mod_weaver.errors import SampleConstraintError


def test_swing_config_range_validation():
    groove.SwingConfig(8, 4)
    with pytest.raises(SampleConstraintError):
        groove.SwingConfig(0, 4)
    with pytest.raises(SampleConstraintError):
        groove.SwingConfig(8, 32)


def test_apply_swing_alternates_speed_by_row_parity():
    pat = Pattern(None, rows=4, channels=2)
    groove.apply_swing(pat, groove.SwingConfig(long_speed=8, short_speed=4))
    assert pat.get(0, 0) == Cell(None, 0, 0x0F, 8)
    assert pat.get(1, 0) == Cell(None, 0, 0x0F, 4)
    assert pat.get(2, 0) == Cell(None, 0, 0x0F, 8)
    assert pat.get(3, 0) == Cell(None, 0, 0x0F, 4)


def test_apply_swing_respects_start_row_parity():
    pat = Pattern(None, rows=3, channels=1)
    groove.apply_swing(pat, groove.SwingConfig(long_speed=8, short_speed=4), start_row=1)
    assert pat.get(0, 0).is_empty
    assert pat.get(1, 0) == Cell(None, 0, 0x0F, 8)   # start_row からの相対で偶数
    assert pat.get(2, 0) == Cell(None, 0, 0x0F, 4)


def test_apply_swing_uses_next_free_channel_when_occupied():
    pat = Pattern(None, rows=1, channels=2)
    pat.replace(0, 0, Cell(24, 1, vol=30))
    groove.apply_swing(pat, groove.SwingConfig())
    assert pat.get(0, 1).effect == 0x0F


def test_retrigger_param():
    assert groove.retrigger_param(3) == 0x93
    with pytest.raises(SampleConstraintError):
        groove.retrigger_param(16)


def test_delay_param():
    assert groove.delay_param(2) == 0xD2
    with pytest.raises(SampleConstraintError):
        groove.delay_param(0)
