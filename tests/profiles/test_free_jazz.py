"""free-jazz の契約・テンポカーブ（ルバート）・検査クリーン性（DESIGN.md §6.11）。"""
from __future__ import annotations

import pytest

from mod_weaver import engine
from mod_weaver.core.verify import verify
from mod_weaver.core.writer import serialize
from mod_weaver.profiles import get_profile
from mod_weaver.genres import free_jazz as fj

profile = get_profile("free-jazz")
SEEDS = list(range(1, 41))


def build(seed):
    return engine.compose_song(profile, seed)


def test_declaration():
    assert profile.id == "free-jazz" and profile.aliases == ()
    assert profile.tempo_policy == "profile"
    assert profile.tempo_choices == (fj.INITIAL_BPM,)
    assert (profile.title, profile.default_filename) == ("Free Jazz", "FreeJazz.mod")


@pytest.mark.parametrize("seed", SEEDS)
def test_structure_and_clean_verification(seed):
    song, plan = build(seed)
    assert plan.order == [0, 1, 2, 3]
    assert len(song.patterns) == 4
    assert [p.kind for p in plan.patterns] == ["movement_a", "movement_b", "climax", "movement_c"]
    assert plan.bpm == fj.INITIAL_BPM
    issues = verify(serialize(song), profile.channel_plan)
    errors = [i for i in issues if i.level == "ERROR"]
    assert errors == [], errors


@pytest.mark.parametrize("seed", SEEDS[:15])
def test_tempo_curve_present_in_every_pattern(seed):
    """tempo_policy="profile" なので apply_tempo は使われず、各 pattern 自身が Fxx を持つ。"""
    song, _ = build(seed)
    for pat in song.patterns:
        found = any(pat.get(r, ch).effect == 0x0F and pat.get(r, ch).param >= 32
                    for r in range(pat.rows) for ch in range(pat.channels))
        assert found


@pytest.mark.parametrize("seed", SEEDS[:15])
def test_tempo_chains_across_movements(seed):
    """movement_a の終端 BPM ≈ movement_b の始端 BPM（EXT-5 の pattern 境界を跨ぐ連続性）。"""
    song, plan = build(seed)

    def bpms(pat):
        return sorted(pat.get(r, ch).param for r in range(pat.rows) for ch in range(pat.channels)
                      if pat.get(r, ch).effect == 0x0F and pat.get(r, ch).param >= 32)

    a_bpms, b_bpms = bpms(song.patterns[0]), bpms(song.patterns[1])
    assert a_bpms and b_bpms
    assert min(a_bpms) <= 83 and max(a_bpms) >= 95      # movement_a: 96 -> 82 付近
    assert min(b_bpms) <= 83 and max(b_bpms) >= 120      # movement_b: 82 -> 126 付近


@pytest.mark.parametrize("seed", SEEDS[:10])
def test_climax_is_denser_than_movement_a(seed):
    song, _ = build(seed)
    density_a = sum(1 for r in range(song.patterns[0].rows) for ch in range(4)
                     if not song.patterns[0].get(r, ch).is_empty)
    density_climax = sum(1 for r in range(song.patterns[2].rows) for ch in range(4)
                          if not song.patterns[2].get(r, ch).is_empty)
    assert density_climax > density_a


def test_build_samples_order_matches_constants():
    specs = fj.build_free_jazz_samples()
    assert list(specs.keys()) == list(fj.SAMPLE_KEYS)


def test_cluster_chord_registers_are_valid_for_each_instrument():
    import random
    rng = random.Random(1)
    for _ in range(50):
        chord = fj._cluster_chord(rng.randint(0, 11), "x", rng)
        assert fj.BASS_REG[0] <= chord.bass <= fj.BASS_REG[1]
        for t in chord.chord_tones:
            assert fj.CLUSTER_REG[0] <= t <= fj.CLUSTER_REG[1]
