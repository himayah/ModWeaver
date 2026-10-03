import pytest

from mod_weaver.core import groove
from mod_weaver.errors import SampleConstraintError


def test_retrigger_param():
    assert groove.retrigger_param(3) == 0x93
    with pytest.raises(SampleConstraintError):
        groove.retrigger_param(16)


def test_delay_param():
    assert groove.delay_param(2) == 0xD2
    with pytest.raises(SampleConstraintError):
        groove.delay_param(0)
