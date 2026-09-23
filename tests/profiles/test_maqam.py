"""maqam の契約・マイクロチューニング・検査クリーン性（GENRE_DESIGN_V2.md §5）。"""
from __future__ import annotations

import pytest

from mod_weaver import engine
from mod_weaver.core.verify import verify
from mod_weaver.core.writer import serialize
from mod_weaver.profiles import get_profile
from mod_weaver.genres import maqam as mq

profile = get_profile("maqam")
SEEDS = list(range(1, 41))


def build(seed):
    return engine.compose_song(profile, seed)


def test_declaration():
    assert profile.id == "maqam" and profile.aliases == ()
    assert profile.rows_per_measure == 16
    assert (profile.title, profile.default_filename) == ("Maqam Rast", "MaqamRast.mod")


@pytest.mark.parametrize("seed", SEEDS)
def test_structure_and_clean_verification(seed):
    song, plan = build(seed)
    assert plan.order == [0, 1, 2, 0, 1, 3]
    assert len(song.patterns) == 4
    assert [p.kind for p in plan.patterns] == ["taqsim", "ostinato_a", "ostinato_b", "coda"]
    assert plan.bpm in profile.tempo_choices
    assert plan.key_pc == mq.KEY_PC
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
def test_taqsim_has_no_percussion(seed):
    song, _ = build(seed)
    pat = song.patterns[0]  # taqsim
    for r in range(pat.rows):
        assert pat.get(r, mq.CH_PERC).sample not in (mq.DUM, mq.TEK)


@pytest.mark.parametrize("seed", SEEDS[:10])
def test_ostinato_a_has_maqsum_usul(seed):
    song, _ = build(seed)
    pat = song.patterns[1]  # ostinato_a
    for m in range(4):
        base = m * 16
        assert pat.get(base + 0, mq.CH_PERC).sample == mq.DUM
        assert pat.get(base + 4, mq.CH_PERC).sample == mq.TEK
        assert pat.get(base + 10, mq.CH_PERC).sample == mq.DUM
        assert pat.get(base + 12, mq.CH_PERC).sample == mq.TEK


def test_neutral_degree_instruments_are_used_across_seeds():
    """中立音程（度数2・6）用の finetune 派生インストゥルメントが実際に使われることを確認する。"""
    found_n3 = found_n7 = False
    for seed in SEEDS:
        song, _ = build(seed)
        for pat in song.patterns:
            for r in range(pat.rows):
                c = pat.get(r, mq.CH_OUD)
                if c.sample == mq.OUD_N3:
                    found_n3 = True
                if c.sample == mq.OUD_N7:
                    found_n7 = True
    assert found_n3 and found_n7


def test_degree_note_stays_in_range():
    lo, hi = mq.MELODY_DEGREE_RANGE
    for d in range(lo, hi + 1):
        t, key = mq._degree_note(d)
        assert 0 <= t <= 35
        assert key in ("oud", "oud_n3", "oud_n7")


def test_neutral_finetune_within_range():
    assert -8 <= mq._neutral_finetune(2) <= 7
    assert -8 <= mq._neutral_finetune(6) <= 7


def test_build_samples_order_matches_constants():
    specs = mq.build_maqam_samples()
    assert list(specs.keys()) == list(mq.SAMPLE_KEYS)
    # oud_n3/oud_n7 は oud の finetune 派生（他フィールドは同一）
    assert specs["oud_n3"].data == specs["oud"].data
    assert specs["oud_n3"].finetune != specs["oud"].finetune
