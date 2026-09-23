from __future__ import annotations

import pytest

from mod_weaver.core import automation
from mod_weaver.core.model import Cell, Pattern
from mod_weaver.errors import PlanError, SampleConstraintError


def test_tempo_curve_validation():
    automation.TempoCurve(100, 140, 0, 10)
    with pytest.raises(SampleConstraintError):
        automation.TempoCurve(20, 140, 0, 10)          # bpm < 32
    with pytest.raises(SampleConstraintError):
        automation.TempoCurve(100, 300, 0, 10)          # bpm > 255
    with pytest.raises(PlanError):
        automation.TempoCurve(100, 140, 10, 10)         # start_row must be < end_row
    with pytest.raises(PlanError):
        automation.TempoCurve(100, 140, 0, 10, curve_type="bogus")


def test_render_tempo_curve_linear_inserts_only_on_change():
    pat = Pattern(None, rows=8, channels=1)
    curve = automation.TempoCurve(100, 104, 0, 4, curve_type="linear")
    automation.render_tempo_curve(pat, curve)
    bpms = [pat.get(r, 0).param for r in range(5) if pat.get(r, 0).effect == 0x0F]
    assert bpms == sorted(set(bpms))                    # 単調増加（値が変わった row にのみ挿入）
    assert bpms[0] == 100 and bpms[-1] == 104
    assert pat.get(5, 0).is_empty                        # end_row 以降は触らない


def test_render_tempo_curve_skips_when_no_free_channel():
    pat = Pattern(None, rows=2, channels=1)
    pat.replace(0, 0, Cell(24, 1, vol=30))               # 唯一のチャンネルが埋まっている
    curve = automation.TempoCurve(100, 120, 0, 1)
    automation.render_tempo_curve(pat, curve)             # 例外を出さず静かにスキップする
    assert pat.get(0, 0) == Cell(24, 1, vol=30)
    assert pat.get(1, 0).effect == 0x0F                  # row1 は空きなので挿入される


def test_portamento_param_basic():
    # period 428 (C-3) -> 214 (C-4) は1オクターブ上（半分の period）
    p = automation.portamento_param(428, 214, rows=2)
    assert 1 <= p <= 255
    assert p == round(abs(428 - 214) / (2 * 6))


def test_portamento_param_same_period_is_minimum():
    assert automation.portamento_param(428, 428, rows=4) == 1


def test_portamento_param_validation():
    with pytest.raises(SampleConstraintError):
        automation.portamento_param(428, 214, rows=-1)
    with pytest.raises(SampleConstraintError):
        automation.portamento_param(428, 214, rows=2, ticks_per_row=0)
