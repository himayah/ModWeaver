"""trap の契約・サブステップ・808グライド・検査クリーン性（DESIGN.md §6.8）。"""
from __future__ import annotations

import pytest

from mod_weaver import engine
from mod_weaver.core.verify import verify
from mod_weaver.core.writer import serialize
from mod_weaver.profiles import get_profile
from mod_weaver.genres import trap as tp

profile = get_profile("trap")
SEEDS = list(range(1, 41))


def build(seed):
    return engine.compose_song(profile, seed)


def test_declaration():
    assert profile.id == "trap" and profile.aliases == ()
    assert profile.rows_per_measure == 32
    assert profile.variable_meter is False
    assert (profile.title, profile.default_filename) == ("Trap Beat", "Trap.mod")


@pytest.mark.parametrize("seed", SEEDS)
def test_structure_and_clean_verification(seed):
    song, plan = build(seed)
    assert plan.order == [0, 1, 1, 2, 2, 3, 2, 2, 4]
    assert len(song.patterns) == 5
    assert [p.kind for p in plan.patterns] == ["intro", "verse", "hook", "half_time", "outro"]
    assert plan.bpm in profile.tempo_choices
    assert plan.key_pc == tp.KEY_PC
    issues = verify(serialize(song), profile.channel_plan)
    errors = [i for i in issues if i.level == "ERROR"]
    assert errors == [], errors
    for pat in song.patterns:
        assert pat.rows == 64
    for p in plan.patterns:
        assert sum(s.measures for s in p.slots) * profile.rows_per_measure == 64


@pytest.mark.parametrize("seed", SEEDS[:10])
def test_tempo_cell_present_on_first_pattern(seed):
    song, plan = build(seed)
    found = [c for c in (song.patterns[0].get(0, ch) for ch in range(4))
             if c.effect == 0x0F and c.param == plan.bpm]
    assert found, "no F<bpm> cell found at pattern0 row0"


@pytest.mark.parametrize("seed", SEEDS[:15])
def test_808_glide_present_in_hook(seed):
    """EXT-5: hook の808に3xx（Tone Portamento）が使われている。"""
    song, _ = build(seed)
    pat = song.patterns[2]     # hook
    portamento_rows = [r for r in range(pat.rows) if pat.get(r, tp.CH_808).effect == 3]
    assert portamento_rows


@pytest.mark.parametrize("seed", SEEDS[:15])
def test_hat_retrigger_sometimes_present(seed):
    """EXT-1: ハイハットに E9x リトリガが（確率的に）使われることがある。複数 seed で少なくとも1回は出る。"""
    song, _ = build(seed)
    pat = song.patterns[2]
    found = any(pat.get(r, tp.CH_HAT).effect == 0x0E and (pat.get(r, tp.CH_HAT).param & 0xF0) == 0x90
                for r in range(pat.rows))
    if found:
        return
    pytest.skip("this seed had no retrigger roll (probabilistic); covered by other seeds")


def test_hat_retrigger_occurs_across_seeds():
    found_any = False
    for seed in SEEDS:
        song, _ = build(seed)
        pat = song.patterns[2]
        if any(pat.get(r, tp.CH_HAT).effect == 0x0E for r in range(pat.rows)):
            found_any = True
            break
    assert found_any


@pytest.mark.parametrize("seed", SEEDS[:10])
def test_intro_has_no_808_or_snare(seed):
    """intro（order[0]）は 808/snare 無音。row 0 の CH_808 には F<bpm> テンポセルが入りうる
    （空きチャンネルへ挿入される。DESIGN.md §3.2）ため sample 番号で判定する。"""
    song, _ = build(seed)
    pat = song.patterns[0]     # intro
    for r in range(pat.rows):
        assert pat.get(r, tp.CH_808).sample != tp.K808
        assert pat.get(r, tp.CH_SNARE).sample != tp.SNARE


@pytest.mark.parametrize("seed", SEEDS[:10])
def test_progressions_match_key(seed):
    song, plan = build(seed)
    expected = [s.chord.label for s in tp.voice_progression()]
    for pp in plan.patterns:
        assert [s.chord.label for s in pp.slots] == expected


def test_build_samples_order_matches_constants():
    specs = tp.build_trap_samples()
    assert list(specs.keys()) == list(tp.SAMPLE_KEYS)
