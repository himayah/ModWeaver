from __future__ import annotations

import pytest

from mod_weaver.core import mixer
from mod_weaver.core.model import Cell, Pattern, Song
from mod_weaver.errors import SampleConstraintError


def test_sidechain_rule_validation():
    mixer.SidechainRule(1, 0)
    with pytest.raises(SampleConstraintError):
        mixer.SidechainRule(0, 0)
    with pytest.raises(SampleConstraintError):
        mixer.SidechainRule(1, 0, duck_ratio=1.5)
    with pytest.raises(SampleConstraintError):
        mixer.SidechainRule(1, 0, release_rows=-1)


def test_apply_sidechain_ducks_and_releases():
    # pad の音量(vol=40)を row0 で確立し、row4 のトリガでダッキングさせる
    # （トリガと同じ row で初めて音量が確立するケースは別テストで検証する）。
    pat = Pattern(None, rows=8, channels=2)
    pat.replace(0, 1, Cell(20, 2, vol=40))       # pad onset
    pat.replace(4, 0, Cell(24, 1, vol=60))       # kick trigger at row4
    song = Song("T", [], [pat], [0])
    rule = mixer.SidechainRule(trigger_sample=1, target_channel=1, duck_ratio=0.5, release_rows=2)
    mixer.apply_sidechain(song, (rule,))
    assert pat.get(4, 1).vol == 20          # 40 * 0.5
    assert pat.get(5, 1).vol == 30          # ramp 20->40 over n=2 rows
    assert pat.get(6, 1).vol == 40          # 元の音量に復帰
    assert pat.get(7, 1).is_empty           # release 区間の外は触らない


def test_apply_sidechain_skips_trigger_with_no_prior_known_volume():
    """トリガと同じ row で初めて音量が確立する場合、「直前の音量」は不明なため安全側でスキップする。"""
    pat = Pattern(None, rows=4, channels=2)
    pat.replace(0, 0, Cell(24, 1, vol=60))       # kick trigger at row0
    pat.replace(0, 1, Cell(20, 2, vol=40))       # pad onset, same row
    song = Song("T", [], [pat], [0])
    rule = mixer.SidechainRule(trigger_sample=1, target_channel=1, duck_ratio=0.5)
    mixer.apply_sidechain(song, (rule,))
    assert pat.get(0, 1) == Cell(20, 2, vol=40)   # 未変更


def test_apply_sidechain_skips_unknown_running_volume():
    pat = Pattern(None, rows=4, channels=2)
    pat.replace(0, 1, Cell(20, 2))               # pad onset with no vol -> unknown volume
    pat.replace(2, 0, Cell(24, 1, vol=60))       # kick trigger at row2
    song = Song("T", [], [pat], [0])
    rule = mixer.SidechainRule(trigger_sample=1, target_channel=1, duck_ratio=0.5)
    mixer.apply_sidechain(song, (rule,))
    assert pat.get(2, 1).is_empty                # 何も置かれない: running volume unknown


def test_apply_sidechain_never_overwrites_non_vol_effect():
    pat = Pattern(None, rows=4, channels=2)
    pat.replace(0, 1, Cell(20, 2, vol=40))
    pat.replace(1, 0, Cell(24, 1, vol=60))       # kick trigger at row1
    pat.replace(2, 1, Cell(20, 2, effect=0x0E, param=0x93))   # deliberate effect at a release row
    song = Song("T", [], [pat], [0])
    rule = mixer.SidechainRule(trigger_sample=1, target_channel=1, duck_ratio=0.5, release_rows=2)
    mixer.apply_sidechain(song, (rule,))
    assert pat.get(1, 1).vol == 20                             # ducked
    assert pat.get(2, 1) == Cell(20, 2, effect=0x0E, param=0x93)   # untouched, release は打ち切り


def test_sample_offset_param():
    assert mixer.sample_offset_param(0, 1000) == 0
    assert mixer.sample_offset_param(256, 1000) == 1
    assert mixer.sample_offset_param(300, 1000) == 1
    with pytest.raises(SampleConstraintError):
        mixer.sample_offset_param(-1, 1000)
    with pytest.raises(SampleConstraintError):
        mixer.sample_offset_param(100000, 100)
    with pytest.raises(SampleConstraintError):
        mixer.sample_offset_param(256 * 300, 1000000)   # param > 255
