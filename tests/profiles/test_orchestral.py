"""orchestral の契約・8chマルチチャンネル(XM)・検査クリーン性（GENRE_DESIGN_V2.md §3）。"""
from __future__ import annotations

import pytest

from mod_weaver import engine
from mod_weaver.core.verify import parse_xm, verify_xm
from mod_weaver.core.writer import serialize_xm
from mod_weaver.profiles import get_profile
from mod_weaver.profiles import orchestral as orch

profile = get_profile("orchestral")
SEEDS = list(range(1, 41))


def build(seed):
    return engine.compose_song(profile, seed)


def test_declaration():
    assert profile.id == "orchestral" and profile.aliases == ()
    assert profile.target_format == "xm"
    assert len(profile.channel_plan) == 8
    assert (profile.title, profile.default_filename) == ("Orchestral Suite", "OrchestralSuite.xm")


@pytest.mark.parametrize("seed", SEEDS)
def test_structure_and_clean_verification(seed):
    song, plan = build(seed)
    assert plan.order == [0, 1, 2, 3, 4]
    assert len(song.patterns) == 5
    assert [p.kind for p in plan.patterns] == ["intro", "theme", "development", "climax", "resolution"]
    assert plan.bpm in profile.tempo_choices
    assert plan.key_pc == orch.KEY_PC
    assert song.patterns[0].channels == 8
    data = serialize_xm(song)
    pm = parse_xm(data)
    assert pm.consumed == len(data)
    issues = verify_xm(data, profile.channel_plan)
    errors = [i for i in issues if i.level == "ERROR"]
    assert errors == [], errors


@pytest.mark.parametrize("seed", SEEDS[:10])
def test_tempo_cell_present_on_first_pattern(seed):
    song, plan = build(seed)
    found = [c for c in (song.patterns[0].get(0, ch) for ch in range(8))
             if c.effect == 0x0F and c.param == plan.bpm]
    assert found, "no F<bpm> cell found at pattern0 row0"


@pytest.mark.parametrize("seed", SEEDS[:10])
def test_intro_is_strings_only(seed):
    """intro は弦楽器のみ。row 0 の CH_WW/CH_BRASS/CH_TIMP には F<bpm> テンポセルが入りうる
    （空きチャンネルへ挿入される。§4.0.1）ため sample 番号で判定する。"""
    song, _ = build(seed)
    pat = song.patterns[0]
    for r in range(pat.rows):
        assert pat.get(r, orch.CH_WW).sample != orch.WW
        assert pat.get(r, orch.CH_BRASS).sample not in (orch.HORN, orch.TRUMPET)
        assert pat.get(r, orch.CH_TIMP).sample not in (orch.TIMPANI, orch.CYMBAL)


@pytest.mark.parametrize("seed", SEEDS[:10])
def test_climax_uses_all_eight_channels(seed):
    song, _ = build(seed)
    pat = song.patterns[3]   # climax
    for ch in range(8):
        assert any(not pat.get(r, ch).is_empty for r in range(pat.rows)), f"channel {ch} unused in climax"


@pytest.mark.parametrize("seed", SEEDS[:10])
def test_climax_uses_trumpet_not_horn(seed):
    song, _ = build(seed)
    pat = song.patterns[3]
    samples = {pat.get(r, orch.CH_BRASS).sample for r in range(pat.rows)}
    samples.discard(0)
    assert samples == {orch.TRUMPET}


@pytest.mark.parametrize("seed", SEEDS[:10])
def test_progressions_match_key(seed):
    song, plan = build(seed)
    expected = [s.chord.label for s in orch.voice_progression()]
    for pp in plan.patterns:
        assert [s.chord.label for s in pp.slots] == expected


def test_pan_values_are_distinct_and_valid():
    specs = orch.build_orchestral_samples()
    pans = [s.pan for s in specs.values()]
    assert all(0 <= p <= 255 for p in pans)
    assert len(set(pans)) >= 6                        # 少なくとも6種類の異なる定位


def test_extra_voices_stay_within_registers():
    from mod_weaver.core.model import ChordDef
    chord = ChordDef(label="C", bass=-6, harmony=6, chord_tones=(19, 23, 26), scale_tones=(19, 23, 26),
                      arp=None, explicit=True)
    alto, sop1, descant, sop2 = orch._extra_voices(chord)
    assert orch.ALTO_REG[0] <= alto <= orch.ALTO_REG[1]
    assert orch.SOP1_REG[0] <= sop1 <= orch.SOP1_REG[1]
    assert orch.DESCANT_REG[0] <= descant <= orch.DESCANT_REG[1]
    assert sop2 == 26                                   # chord_tones の最高音


def test_build_samples_order_matches_constants():
    specs = orch.build_orchestral_samples()
    assert list(specs.keys()) == list(orch.SAMPLE_KEYS)
    assert specs["vln2"].data == specs["vln1"].data      # vln2 は vln1 の finetune 派生
    assert specs["vln2"].finetune != specs["vln1"].finetune
