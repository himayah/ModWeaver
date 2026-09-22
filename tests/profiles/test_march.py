"""march の文法・音域・契約（設計書 §8.5、§11.3）。"""
from __future__ import annotations

import pytest

from mod_weaver import engine
from mod_weaver.core.verify import verify
from mod_weaver.core.writer import serialize
from mod_weaver.profiles import get_profile
from mod_weaver.profiles import march as mp
from tests.helpers import iter_cells

profile = get_profile("march")
SEEDS = list(range(1, 31))

# パターン種別 -> picc の melody 音域（begin_pattern と同じ対応）
MELODY_REG_BY_KIND = {
    "intro": mp.MELODY_MAIN, "a": mp.MELODY_MAIN, "a2": mp.MELODY_MAIN,
    "trio": mp.MELODY_TRIO, "trio2": mp.MELODY_TRIO2, "coda": mp.MELODY_TRIO2,
}


def build(seed):
    return engine.compose_song(profile, seed)


def test_declaration():
    assert profile.id == "march" and profile.aliases == ()
    assert profile.tempo_choices == (118, 119, 120, 121, 122) and profile.rows_per_measure == 8
    assert (profile.title, profile.default_filename) == ("Military March", "MilitaryMarch.mod")


@pytest.mark.parametrize("seed", SEEDS)
def test_structure_and_clean_verification(seed):
    song, plan = build(seed)
    assert plan.order == [0, 1, 2, 1, 2, 3, 4, 3, 4, 5]
    assert len(song.patterns) == 6 and len(plan.order) == 10
    assert [p.kind for p in plan.patterns] == ["intro", "a", "a2", "trio", "trio2", "coda"]
    assert plan.bpm in profile.tempo_choices
    assert plan.key_pc in mp.KEY_CHOICES
    assert verify(serialize(song), profile.channel_plan) == []
    for p in plan.patterns:
        assert sum(s.measures for s in p.slots) == 8


def test_tempo_cell_on_first_empty_channel():
    song, plan = build(3)
    # intro row 0 の Ch3 (harmony) は section が置かれるため、テンポは残る空きチャンネルに入る
    found = [c for c in (song.patterns[0].get(0, ch) for ch in range(4))
             if c.effect == 0x0F and c.param == plan.bpm]
    assert found, "no F<bpm> cell found at pattern0 row0"


@pytest.mark.parametrize("seed", SEEDS[:12])
def test_trio_is_subdominant_of_main_key(seed):
    song, plan = build(seed)
    trio_tonic = (plan.key_pc + mp.TRIO_OFFSET) % 12
    assert plan.patterns[3].key_offset == mp.TRIO_OFFSET
    assert plan.patterns[4].key_offset == mp.TRIO_OFFSET
    expected = mp.voice_march_progression("trio", trio_tonic)
    assert [s.chord.label for s in plan.patterns[3].slots] == [s.chord.label for s in expected]
    assert [s.chord.label for s in plan.patterns[4].slots] == [s.chord.label for s in expected]


@pytest.mark.parametrize("seed", SEEDS[:12])
def test_strain_progressions_match_key(seed):
    song, plan = build(seed)
    kp = plan.key_pc
    assert [s.chord.label for s in plan.patterns[1].slots] == \
        [s.chord.label for s in mp.voice_march_progression("sousa", kp)]
    for idx in (0, 2, 5):       # intro / a2 / coda はいずれも heroic
        assert [s.chord.label for s in plan.patterns[idx].slots] == \
            [s.chord.label for s in mp.voice_march_progression("heroic", kp)]


@pytest.mark.parametrize("seed", SEEDS[:10])
def test_oom_pah_full_band_in_strain(seed):
    song, _ = build(seed)
    pat = song.patterns[1]                    # "a" (sousa)
    for m in range(8):
        base = m * 8
        assert pat.get(base, mp.CH_BASS).sample == mp.TUBA
        assert pat.get(base + 4, mp.CH_HARM).sample == mp.HORN
        drum0 = pat.get(base, mp.CH_DRUM)
        assert drum0.sample in (mp.BD, mp.CRASH)          # m0 は crash が bd を置換
        assert pat.get(base + 4, mp.CH_DRUM).sample == mp.SD


@pytest.mark.parametrize("seed", SEEDS[:10])
def test_crash_replaces_bd_at_measure0(seed):
    song, _ = build(seed)
    for idx in (1, 2):                        # a / a2: m0 に crash
        pat = song.patterns[idx]
        c = pat.get(0, mp.CH_DRUM)
        assert c.sample == mp.CRASH and c.vol == 64


@pytest.mark.parametrize("seed", SEEDS[:10])
def test_snare_roll_at_phrase_end(seed):
    song, _ = build(seed)
    for idx in (1, 2, 4):                     # a / a2 / trio2 の m7 (row 56-63)
        pat = song.patterns[idx]
        vols = [pat.get(56 + r, mp.CH_DRUM).vol for r in range(4, 8)]
        assert vols == [36, 43, 51, 58] and all(pat.get(56 + r, mp.CH_DRUM).sample == mp.SD for r in range(4, 8))


@pytest.mark.parametrize("seed", SEEDS[:10])
def test_trio_has_no_crash_or_roll_and_lighter_drums(seed):
    song, _ = build(seed)
    pat = song.patterns[3]
    for m in range(8):
        base = m * 8
        assert pat.get(base, mp.CH_DRUM).sample == mp.BD and pat.get(base, mp.CH_DRUM).vol == 48
        assert pat.get(base + 4, mp.CH_DRUM).sample == mp.SD and pat.get(base + 4, mp.CH_DRUM).vol == 38
        horn = pat.get(base + 4, mp.CH_HARM)
        assert horn.sample == mp.HORN and horn.vol == 34 and not horn.has_effect  # non-arp（intensity<0.7）
    assert all(pat.get(r, mp.CH_DRUM).sample != mp.CRASH for r in range(64))


@pytest.mark.parametrize("seed", SEEDS[:8])
def test_intro_grammar(seed):
    song, _ = build(seed)
    pat = song.patterns[0]
    assert pat.get(0, mp.CH_DRUM).sample == mp.CRASH and pat.get(0, mp.CH_DRUM).vol == 64
    assert pat.get(0, mp.CH_HARM).sample == mp.SECTION
    for r in range(8, 24):                    # m1, m2: ドラムなし
        assert pat.get(r, mp.CH_DRUM).is_empty
    light_sd = pat.get(3 * 8 + 4, mp.CH_DRUM)
    assert light_sd.sample == mp.SD and light_sd.vol == 30
    for m in range(4, 8):                     # m4 以降は oom-pah
        base = m * 8
        assert pat.get(base, mp.CH_BASS).sample == mp.TUBA


@pytest.mark.parametrize("seed", SEEDS[:8])
def test_trio2_sustained_section_and_crash_at_m4(seed):
    song, _ = build(seed)
    pat = song.patterns[4]
    for m in range(4):
        assert pat.get(m * 8, mp.CH_HARM).sample == mp.SECTION
    assert pat.get(4 * 8, mp.CH_DRUM).sample == mp.CRASH


@pytest.mark.parametrize("seed", SEEDS[:8])
def test_coda_final_chord(seed):
    song, _ = build(seed)
    pat = song.patterns[5]
    last = 7 * 8
    assert pat.get(last, mp.CH_DRUM).sample == mp.CRASH
    assert pat.get(last, mp.CH_BASS).sample == mp.TUBA
    assert pat.get(last, mp.CH_HARM).sample == mp.SECTION
    picc = pat.get(last, mp.CH_MEL)
    assert picc.sample == mp.PICC and picc.note is not None
    assert pat.get(0, mp.CH_DRUM).sample == mp.CRASH        # m0 にも crash


@pytest.mark.parametrize("seed", SEEDS)
def test_registers(seed):
    song, plan = build(seed)
    tuba, horn, section, picc = (song.samples[i - 1] for i in (mp.TUBA, mp.HORN, mp.SECTION, mp.PICC))
    for p, r, ch, c in iter_cells(song):
        if c.note is None:
            continue
        kind = plan.patterns[p].kind
        if c.sample == mp.TUBA:
            assert mp.BASS_REG[0] <= c.note + tuba.shift <= mp.BASS_REG[1]
        elif c.sample == mp.HORN:
            assert mp.HARMONY_REG[0] <= c.note + horn.shift <= mp.HARMONY_REG[1]
            assert c.effect != 0 or c.param == 0 or c.note + max(c.param >> 4, c.param & 15) <= 35
        elif c.sample == mp.SECTION:
            assert mp.HARMONY_REG[0] <= c.note + section.shift <= mp.HARMONY_REG[1]
        elif c.sample == mp.PICC:
            lo, hi = MELODY_REG_BY_KIND[kind]
            assert lo <= c.note + picc.shift <= hi


def test_deterministic_and_seed_sensitive():
    assert serialize(build(9)[0]) == serialize(build(9)[0]) != serialize(build(10)[0])


def test_generate_writes_verified_file(tmp_path):
    res = engine.generate(profile, 8, tmp_path / "m.mod")
    assert res.issues == [] and res.path.stat().st_size < 200_000


def test_all_samples_used_across_seeds():
    used = set()
    for seed in range(1, 15):
        song, _ = build(seed)
        for _, _, _, c in iter_cells(song):
            if c.sample:
                used.add(c.sample)
    assert used == {mp.BD, mp.SD, mp.CRASH, mp.TUBA, mp.HORN, mp.SECTION, mp.PICC}
