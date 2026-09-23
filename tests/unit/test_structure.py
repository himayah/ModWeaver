from __future__ import annotations

import pytest

from mod_weaver.core import structure
from mod_weaver.errors import PlanError


def test_polymetric_row_wraps():
    assert structure.polymetric_row(0, 16) == 0
    assert structure.polymetric_row(15, 16) == 15
    assert structure.polymetric_row(16, 16) == 0
    assert structure.polymetric_row(20, 12) == 8


def test_polymetric_row_rejects_non_positive_cycle():
    with pytest.raises(PlanError):
        structure.polymetric_row(0, 0)
