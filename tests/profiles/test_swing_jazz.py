"""swing-jazz の契約・構造・検査クリーン性（GENRE_DESIGN_V2.md §1）。"""
from __future__ import annotations

import pytest

from mod_weaver import engine
from mod_weaver.core.verify import verify
from mod_weaver.core.writer import serialize
from mod_weaver.profiles import get_profile
from mod_weaver.profiles import swing_jazz as sj

profile = get_profile("swing-jazz")
SEEDS = list(range(1, 41))


def build(seed):
    return engine.compose_song(profile, seed)


def test_declaration():
    assert profile.id == "swing-jazz" and profile.aliases == ()
    assert profile.rows_per_measure == 8
    assert profile.tempo_choices == (152, 156, 160, 164, 168)
    assert profile.variable_meter is False
    assert (profile.title, profile.default_filename) == ("Swing Jazz", "SwingJazz.mod")


@pytest.mark.parametrize("seed", SEEDS)
def test_structure_and_clean_verification(seed):
    song, plan = build(seed)
    assert plan.order == [0, 1, 1, 2, 1, 3, 3, 4, 3, 1, 1, 2, 5]
    assert len(song.patterns) == 6 and len(plan.order) == 13
    assert [p.kind for p in plan.patterns] == ["intro", "a", "b", "solo_a", "solo_b", "out"]
    assert plan.bpm in profile.tempo_choices
    assert plan.key_pc == sj.KEY_PC
    issues = verify(serialize(song), profile.channel_plan)
    errors = [i for i in issues if i.level == "ERROR"]
    assert errors == [], errors
    for p in plan.patterns:
        assert sum(s.measures for s in p.slots) * profile.rows_per_measure == 64


@pytest.mark.parametrize("seed", SEEDS[:10])
def test_tempo_cell_present_on_first_pattern(seed):
    song, plan = build(seed)
    found = [c for c in (song.patterns[0].get(0, ch) for ch in range(4))
             if c.effect == 0x0F and c.param == plan.bpm]
    assert found, "no F<bpm> cell found at pattern0 row0"


@pytest.mark.parametrize("seed", SEEDS[:10])
def test_swing_speed_cells_present(seed):
    """EXT-1: 少なくとも1つの pattern に long/short 双方の Speed(F0x) 交互挿入が見つかる。"""
    song, _ = build(seed)
    found_long = found_short = False
    for pat in song.patterns:
        for row in range(pat.rows):
            for ch in range(pat.channels):
                c = pat.get(row, ch)
                if c.effect == 0x0F and c.param == sj.SWING_CONFIG.long_speed:
                    found_long = True
                if c.effect == 0x0F and c.param == sj.SWING_CONFIG.short_speed:
                    found_short = True
    assert found_long and found_short


@pytest.mark.parametrize("seed", SEEDS[:10])
def test_progressions_match_key(seed):
    song, plan = build(seed)
    expected_a = [s.chord.label for s in sj.voice_progression("a")]
    expected_b = [s.chord.label for s in sj.voice_progression("b")]
    assert [s.chord.label for s in plan.patterns[1].slots] == expected_a   # "a"
    assert [s.chord.label for s in plan.patterns[2].slots] == expected_b   # "b"
    assert [s.chord.label for s in plan.patterns[3].slots] == expected_a   # "solo_a"
    assert [s.chord.label for s in plan.patterns[4].slots] == expected_b   # "solo_b"


@pytest.mark.parametrize("seed", SEEDS[:10])
def test_head_pattern_has_full_texture(seed):
    """"a" pattern の各 measure でライド・ベースが必ず row 0 に鳴っている。"""
    song, _ = build(seed)
    pat = song.patterns[1]
    for m in range(8):
        base = m * 8
        assert pat.get(base, sj.CH_DRUM).sample == sj.RIDE
        assert pat.get(base, sj.CH_BASS).sample == sj.BASS


def test_build_samples_order_matches_constants():
    specs = sj.build_swing_jazz_samples()
    assert list(specs.keys()) == list(sj.SAMPLE_KEYS)
