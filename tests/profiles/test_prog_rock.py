"""prog-rock の契約・可変小節構造・検査クリーン性（GENRE_DESIGN_V2.md §2）。"""
from __future__ import annotations

import pytest

from mod_weaver import engine
from mod_weaver.core.verify import verify
from mod_weaver.core.writer import serialize
from mod_weaver.profiles import get_profile
from mod_weaver.profiles import prog_rock as pr

profile = get_profile("prog-rock")
SEEDS = list(range(1, 41))


def build(seed):
    return engine.compose_song(profile, seed)


def test_declaration():
    assert profile.id == "prog-rock" and profile.aliases == ()
    assert profile.rows_per_measure == 16
    assert profile.variable_meter is True
    assert (profile.title, profile.default_filename) == ("Prog Rock", "ProgRock.mod")


@pytest.mark.parametrize("seed", SEEDS)
def test_structure_and_clean_verification(seed):
    song, plan = build(seed)
    assert plan.order == [0, 1, 1, 2, 1, 3, 2, 4]
    assert len(song.patterns) == 5
    assert [p.kind for p in plan.patterns] == ["intro", "verse", "chorus", "breakdown", "outro"]
    assert plan.bpm in profile.tempo_choices
    assert plan.key_pc == pr.KEY_PC
    issues = verify(serialize(song), profile.channel_plan)
    errors = [i for i in issues if i.level == "ERROR"]
    assert errors == [], errors
    for pat in song.patterns:
        assert pat.rows == 64            # 物理パターンは常に64row（EXT-2でも不変）


@pytest.mark.parametrize("seed", SEEDS[:15])
def test_riff_patterns_use_variable_measure_lengths(seed):
    """riff（intro/verse/outro）は 14+14+10=38 row。 D00 が row37 に入る。"""
    song, plan = build(seed)
    for idx in (0, 1, 4):    # intro, verse, outro
        assert [s.rows for s in plan.patterns[idx].slots] == [14, 14, 10]
        pat = song.patterns[idx]
        found = [pat.get(37, ch) for ch in range(4) if pat.get(37, ch).effect == 0x0D]
        assert found, f"no D00 pattern-break found at pattern {idx} row 37"


@pytest.mark.parametrize("seed", SEEDS[:15])
def test_breakdown_is_all_5_8(seed):
    song, plan = build(seed)
    bd = plan.patterns[3]
    assert [s.rows for s in bd.slots] == [10] * 6
    pat = song.patterns[3]
    found = [pat.get(59, ch) for ch in range(4) if pat.get(59, ch).effect == 0x0D]
    assert found, "no D00 pattern-break found at breakdown row 59"


@pytest.mark.parametrize("seed", SEEDS[:15])
def test_chorus_is_full_64_rows_no_break(seed):
    song, plan = build(seed)
    assert sum(s.rows * s.measures for s in plan.patterns[2].slots) == 64
    pat = song.patterns[2]
    assert not any(pat.get(63, ch).effect == 0x0D for ch in range(4))


@pytest.mark.parametrize("seed", SEEDS[:10])
def test_tempo_cell_present_on_first_pattern(seed):
    song, plan = build(seed)
    found = [c for c in (song.patterns[0].get(0, ch) for ch in range(4))
             if c.effect == 0x0F and c.param == plan.bpm]
    assert found, "no F<bpm> cell found at pattern0 row0"


@pytest.mark.parametrize("seed", SEEDS[:10])
def test_progressions_match_key(seed):
    song, plan = build(seed)
    expected_riff = [s.chord.label for s in pr.riff_slots()]
    expected_chorus = [s.chord.label for s in pr.chorus_slots()]
    expected_breakdown = [s.chord.label for s in pr.breakdown_slots()]
    assert [s.chord.label for s in plan.patterns[0].slots] == expected_riff       # intro
    assert [s.chord.label for s in plan.patterns[1].slots] == expected_riff       # verse
    assert [s.chord.label for s in plan.patterns[2].slots] == expected_chorus     # chorus
    assert [s.chord.label for s in plan.patterns[3].slots] == expected_breakdown  # breakdown
    assert [s.chord.label for s in plan.patterns[4].slots] == expected_riff       # outro


def test_build_samples_order_matches_constants():
    specs = pr.build_prog_rock_samples()
    assert list(specs.keys()) == list(pr.SAMPLE_KEYS)
