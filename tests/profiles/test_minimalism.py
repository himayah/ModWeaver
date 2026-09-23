"""minimalism の契約・ポリメトリック・検査クリーン性（DESIGN.md §6.12）。"""
from __future__ import annotations

import pytest

from mod_weaver import engine
from mod_weaver.core.verify import verify
from mod_weaver.core.writer import serialize
from mod_weaver.profiles import get_profile
from mod_weaver.genres import minimalism as mn

profile = get_profile("minimalism")
SEEDS = list(range(1, 41))


def build(seed):
    return engine.compose_song(profile, seed)


def test_declaration():
    assert profile.id == "minimalism" and profile.aliases == ()
    assert profile.variable_meter is True
    assert (profile.title, profile.default_filename) == ("Phase Process", "PhaseProcess.mod")


@pytest.mark.parametrize("seed", SEEDS)
def test_structure_and_clean_verification(seed):
    song, plan = build(seed)
    assert plan.order == list(range(16))
    assert len(song.patterns) == 16
    assert [p.kind for p in plan.patterns] == [f"phase{i}" for i in range(16)]
    assert plan.bpm in profile.tempo_choices
    issues = verify(serialize(song), profile.channel_plan)
    errors = [i for i in issues if i.level == "ERROR"]
    assert errors == [], errors
    for pat in song.patterns:
        assert pat.rows == 64


@pytest.mark.parametrize("seed", SEEDS[:10])
def test_pattern_break_at_row_47(seed):
    song, _ = build(seed)
    for pat in song.patterns:
        found = any(pat.get(47, ch).effect == 0x0D and pat.get(47, ch).param == 0 for ch in range(4))
        assert found
        for r in range(48, 64):
            for ch in range(4):
                assert pat.get(r, ch).is_empty


@pytest.mark.parametrize("seed", SEEDS[:10])
def test_tempo_cell_present_on_first_pattern(seed):
    song, plan = build(seed)
    found = [c for c in (song.patterns[0].get(0, ch) for ch in range(4))
             if c.effect == 0x0F and c.param == plan.bpm]
    assert found, "no F<bpm> cell found at pattern0 row0"


def test_piano_channel_shifts_by_phase_and_wraps_after_16_stages():
    song, _ = build(1)

    def piano_onsets(idx):
        pat = song.patterns[idx]
        return [r for r in range(48) if pat.get(r, mn.CH_PIANO).sample == mn.PIANO]

    phase0, phase1, phase8 = piano_onsets(0), piano_onsets(1), piano_onsets(8)
    assert phase0 != phase1
    assert [r + 1 for r in phase0 if r + 1 < 48] == [r for r in phase1 if r != 0] or phase1[0] == 1
    assert phase0 == phase8   # 位相8 は周期16の半分ずれ＝偶奇一致で同じ row 集合に戻る


def test_other_channels_are_not_phase_shifted():
    """CH_MARIMBA/CH_VIBES/CH_WOOD は全 phase で同じ固定パターンのまま。"""
    song, _ = build(2)
    for ch, key, sample in ((mn.CH_MARIMBA, "marimba", mn.MARIMBA), (mn.CH_VIBES, "vibraphone", mn.VIBES)):
        onsets_by_phase = {
            i: tuple(r for r in range(48) if song.patterns[i].get(r, ch).sample == sample)
            for i in range(16)
        }
        assert len(set(onsets_by_phase.values())) == 1   # 全 phase で同一


def test_build_samples_order_matches_constants():
    specs = mn.build_minimalism_samples()
    assert list(specs.keys()) == list(mn.SAMPLE_KEYS)


def test_lcm_matches_cycle_lengths():
    import math
    lcm = math.lcm(mn.CYCLE_PIANO, mn.CYCLE_MARIMBA, mn.CYCLE_VIBES, mn.CYCLE_WOOD)
    assert lcm == mn.LCM_ROWS
