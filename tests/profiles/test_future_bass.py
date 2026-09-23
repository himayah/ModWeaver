"""future-bass の契約・サイドチェイン・検査クリーン性（GENRE_DESIGN_V2.md §7）。"""
from __future__ import annotations

import pytest

from mod_weaver import engine
from mod_weaver.core.verify import verify
from mod_weaver.core.writer import serialize
from mod_weaver.profiles import get_profile
from mod_weaver.genres import future_bass as fb

profile = get_profile("future-bass")
SEEDS = list(range(1, 41))


def build(seed):
    return engine.compose_song(profile, seed)


def test_declaration():
    assert profile.id == "future-bass" and profile.aliases == ()
    assert profile.rows_per_measure == 16
    assert (profile.title, profile.default_filename) == ("Future Bass", "FutureBass.mod")


@pytest.mark.parametrize("seed", SEEDS)
def test_structure_and_clean_verification(seed):
    song, plan = build(seed)
    assert plan.order == [0, 0, 1, 2, 2, 3, 2, 2, 4]
    assert len(song.patterns) == 5
    assert [p.kind for p in plan.patterns] == ["intro_chop", "buildup", "drop", "breakdown", "outro"]
    assert plan.bpm in profile.tempo_choices
    assert plan.key_pc == fb.KEY_PC
    issues = verify(serialize(song), profile.channel_plan)
    errors = [i for i in issues if i.level == "ERROR"]
    assert errors == [], errors


@pytest.mark.parametrize("seed", SEEDS[:10])
def test_tempo_cell_present_on_first_pattern(seed):
    song, plan = build(seed)
    found = [c for c in (song.patterns[0].get(0, ch) for ch in range(4))
             if c.effect == 0x0F and c.param == plan.bpm]
    assert found, "no F<bpm> cell found at pattern0 row0"


@pytest.mark.parametrize("seed", SEEDS[:10])
def test_drop_has_four_on_the_floor_kick_or_clap(seed):
    song, _ = build(seed)
    pat = song.patterns[2]     # drop
    for m in range(4):
        base = m * 16
        for row in fb.FOUR_ON_FLOOR:
            assert pat.get(base + row, fb.CH_KICK).sample in (fb.KICK, fb.CLAP)


@pytest.mark.parametrize("seed", SEEDS[:10])
def test_sidechain_ducks_bass_and_chord_in_drop(seed):
    """drop の少なくとも1箇所で、kick/clap トリガ後にベース/コードの音量が下がっていることを確認する。"""
    song, _ = build(seed)
    pat = song.patterns[2]
    ducked_bass = any(
        pat.get(r, fb.CH_BASS).vol is not None and pat.get(r, fb.CH_BASS).vol < 56
        for r in range(pat.rows)
    )
    ducked_chord = any(
        pat.get(r, fb.CH_CHORD).vol is not None and pat.get(r, fb.CH_CHORD).vol < 56
        for r in range(pat.rows)
    )
    assert ducked_bass and ducked_chord


@pytest.mark.parametrize("seed", SEEDS[:10])
def test_breakdown_has_no_kick(seed):
    song, _ = build(seed)
    pat = song.patterns[3]     # breakdown
    for r in range(pat.rows):
        assert pat.get(r, fb.CH_KICK).is_empty


def test_build_samples_order_matches_constants():
    specs = fb.build_future_bass_samples()
    assert list(specs.keys()) == list(fb.SAMPLE_KEYS)
