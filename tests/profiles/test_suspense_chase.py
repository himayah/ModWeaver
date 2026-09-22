"""suspense-chase の文法・音域・契約（設計書 §8.4、§11.3）。"""
from __future__ import annotations

import pytest

from mod_weaver import engine
from mod_weaver.core.model import Cell
from mod_weaver.core.verify import verify
from mod_weaver.core.writer import serialize
from mod_weaver.profiles import get_profile
from mod_weaver.profiles import suspense_common as sc
from tests.helpers import iter_cells

profile = get_profile("suspense-chase")
SEEDS = list(range(1, 31))
OFF = Cell(None, 0, vol=0)


def build(seed):
    return engine.compose_song(profile, seed)


def anvil_rows(pat):
    return [r for r in range(pat.rows) if pat.get(r, 0).sample == sc.ANVIL]


def test_declaration():
    assert profile.id == "suspense-chase" and profile.aliases == ()
    assert profile.tempo_choices == (138, 140, 142, 144, 146, 148) and profile.rows_per_measure == 16
    assert (profile.title, profile.default_filename) == ("Suspense Chase", "SuspenseChase.mod")


@pytest.mark.parametrize("seed", SEEDS)
def test_structure_and_clean_verification(seed):
    song, plan = build(seed)
    assert plan.order == [0, 1, 2, 3, 1, 3, 4, 5] and len(song.patterns) == 6 and len(plan.order) == 8
    assert [p.kind for p in plan.patterns] == ["intro", "a", "a", "b", "climax", "outro"]
    assert plan.bpm in profile.tempo_choices
    assert verify(serialize(song), profile.channel_plan) == []
    labels = lambda i: [s.chord.label for s in plan.patterns[i].slots]
    assert labels(1) == labels(2) == labels(0) == labels(5) == ["Cdim", "Db/C", "Cdim", "B/C"]      # A = pedal
    assert labels(3) == labels(4) == ["Cm", "F#dim", "Fm", "Bdim"]                                 # B = tritone


def test_tempo_cell_on_first_empty_channel():
    song, plan = build(2)
    assert song.patterns[0].get(0, 0) == Cell(None, 0, 0x0F, plan.bpm)     # intro row 0 の Ch1 は空


@pytest.mark.parametrize("seed", SEEDS)
def test_every_shock_hit_has_guard(seed):
    # climax は例外: 16 分 pizz crescendo が全 row を占め、anvil も無音を挟まず連打される
    # 「息もつかせぬ追走」自体が意図（test_climax_grammar で固定）なので guard の対象外。
    song, plan = build(seed)
    guarded = {sc.HEART, sc.PIZZ, sc.LEAD}
    for p, pat in enumerate(song.patterns):
        if plan.patterns[p].kind == "climax":
            continue
        for r in anvil_rows(pat):
            for rr in range(max(0, r - sc.SHOCK_GUARD_ROWS), r):
                for ch in range(4):
                    c = pat.get(rr, ch)
                    assert not (c.note is not None and c.sample in guarded), (seed, p, r, rr, ch)


@pytest.mark.parametrize("seed", SEEDS)
def test_a_patterns_silence_run_then_anvil(seed):
    song, plan = build(seed)
    silent = []
    for idx in (1, 2):
        pat = song.patterns[idx]
        anv = anvil_rows(pat)
        assert len(anv) == 1 and anv[0] % 16 == 0 and pat.get(anv[0], 0).vol == 64
        s = anv[0] // 16 - 1
        silent.append(s)
        for r in range(s * 16 + 8, s * 16 + 16):                      # silence run: 新規 note なし
            assert all(pat.get(r, c).note is None for c in range(4)), (idx, r)
        assert [pat.get(s * 16 + 8, c) for c in (1, 2, 3)] == [OFF] * 3     # 持続音を消音
        assert pat.get(s * 16 + 7, 1).note is not None                     # 直前までは鳴っている
    assert silent == [2, 1]                                                # A1 と A2 で位置が異なる


@pytest.mark.parametrize("seed", SEEDS[:12])
def test_a_patterns_differ_in_stab_positions(seed):
    song, _ = build(seed)
    stabs = lambda pat: [r for r in range(64) if pat.get(r, 3).sample == sc.PIZZ and pat.get(r, 3).note is not None]
    a1, a2 = stabs(song.patterns[1]), stabs(song.patterns[2])
    assert len(a1) == 2 and len(a2) == 2
    for idx, rows in ((1, a1), (2, a2)):
        pat = song.patterns[idx]
        assert all(pat.get(r, 3).vol == 60 for r in rows)
        for r in rows:
            n = pat.get(r, 3).note
            assert sc.PIZZ_REG[0] <= n <= sc.PIZZ_REG[1]
    assert a1 != a2 or seed % 5 == 0        # ほぼ常に異なる（偶然一致は許容）


def test_stab_positions_vary_across_seeds():
    seen = set()
    for s in range(1, 30):
        pat = build(s)[0].patterns[1]
        seen.add(tuple(r for r in range(64) if pat.get(r, 3).sample == sc.PIZZ and pat.get(r, 3).note is not None))
    assert len(seen) > 3


@pytest.mark.parametrize("seed", SEEDS[:8])
def test_intro_grammar(seed):
    song, _ = build(seed)
    pat = song.patterns[0]
    heart = [r for r in range(64) if pat.get(r, 0).sample == sc.HEART]
    assert heart == list(range(32, 64, 4)) and all(pat.get(r, 0).vol == 36 for r in heart)
    ost = [pat.get(r, 2) for r in range(0, 64, 2)]
    vols = [c.vol for c in ost]
    assert len(ost) == 32 and vols[0] == 16 and vols[-1] == 56 and vols == sorted(vols)      # 単調増加の crescendo
    assert len({c.note for c in ost}) == 1 and sc.PIZZ_REG[0] <= ost[0].note <= sc.PIZZ_REG[1]
    assert all(pat.get(r, 2).is_empty for r in range(1, 64, 2))


@pytest.mark.parametrize("seed", SEEDS[:8])
def test_a_grammar_pulse_drone_ostinato(seed):
    song, plan = build(seed)
    pat = song.patterns[1]
    anv = anvil_rows(pat)[0]
    s = anv // 16 - 1
    resume = anv + sc.anvil_clear_row(plan.bpm)
    for m in (0, 1):                                              # anvil と無関係な measure
        base = m * 16
        assert [pat.get(base + r, 0).vol for r in (0, 4, 8, 12)] == [56] * 4          # 毎拍
        assert [pat.get(base + r, 0).vol for r in (2, 6, 10, 14)] == [None, 34, None, 34]   # odd 拍のみ dub
        drone = [pat.get(base + r, 1) for r in range(0, 16, 2)]
        assert [c.vol for c in drone] == [52, 44] * 4 and {c.note for c in drone} == {24}    # pedal: logical 0
        ost = [pat.get(base + r, 2) for r in range(0, 16, 2)]
        base_note = ost[0].note
        assert [c.note - base_note for c in ost] == [0, 0, 1, 0, 0, 0, 6, 0]
        assert [c.vol for c in ost] == [56, 44, 56, 44, 56, 44, 56, 44]
    assert all(pat.get(r, 0).is_empty for r in range(anv + 1, resume))          # anvil の余韻を心拍で切らない
    assert pat.get(resume, 0).vol == 56
    assert pat.get(anv, 1).vol == 52 and pat.get(anv, 2).vol == 56               # 衝撃と同時に再開


@pytest.mark.parametrize("seed", SEEDS[:8])
def test_b_grammar(seed):
    song, _ = build(seed)
    pat = song.patterns[3]
    lead = song.samples[sc.LEAD - 1]
    strings = song.samples[sc.STRINGS - 1]
    for m in range(4):
        base = m * 16
        drone = [pat.get(base + r, 1) for r in range(0, 16, 2)]
        assert [c.vol for c in drone] == [52, 44] * 4
        st = pat.get(base, 2)
        assert st.sample == sc.STRINGS and st.vol is None and st.has_effect
        assert sc.HARMONY_REG[0] <= st.note + strings.shift <= sc.HARMONY_REG[1]
        assert all(pat.get(base + r, 2).is_empty for r in range(1, 16))            # ostinato は退避
        onsets = [r for r in range(16) if pat.get(base + r, 3).note is not None]
        assert onsets in ([0, 3, 6, 10], [0, 2, 4, 8, 10, 12])
        for r in onsets:
            assert sc.LEAD_REG[0] <= pat.get(base + r, 3).note + lead.shift <= sc.LEAD_REG[1]
    assert pat.get(63, 3) == OFF


@pytest.mark.parametrize("seed", SEEDS[:8])
def test_climax_grammar(seed):
    song, plan = build(seed)
    pat = song.patterns[4]
    bpm = plan.bpm
    assert anvil_rows(pat) == [0, 16, 32, 48]
    sw = [r for r in range(64) if pat.get(r, 0).sample == sc.SWOOSH]
    assert sw == [48 + 16 - round(0.9 / (15 / bpm))] and sw[0] % 16 in (7, 8)
    assert all(pat.get(r, 0).is_empty for r in range(sw[0] + 1, 64))               # swoosh を心拍で切らない
    ost = [pat.get(r, 2).vol for r in range(64)]
    assert ost[0] == 30 and ost[-1] == 60 and ost == sorted(ost)                    # 16 分 crescendo（毎 row）
    assert all(pat.get(r, 2).sample == sc.PIZZ for r in range(64))
    lead = song.samples[sc.LEAD - 1]
    notes = [pat.get(r, 3).note + lead.shift for r in range(64) if pat.get(r, 3).note is not None]
    assert notes and min(notes) >= 30                                               # 高音域
    assert all(pat.get(r, 1).vol == 52 for r in range(0, 64, 2))


@pytest.mark.parametrize("seed", SEEDS[:8])
def test_outro_grammar(seed):
    song, _ = build(seed)
    pat = song.patterns[5]
    assert pat.get(0, 0).sample == sc.ANVIL and pat.get(0, 0).vol == 64
    heart = {r: pat.get(r, 0).vol for r in range(64) if pat.get(r, 0).sample == sc.HEART}
    assert list(heart) == [16, 24, 36, 52] and list(heart.values()) == sorted(heart.values(), reverse=True)
    assert heart[16] == 40 and heart[52] == 14
    assert pat.get(0, 2).sample == sc.STRINGS and pat.get(0, 2).vol == 20
    assert pat.get(0, 1) == OFF                                                     # climax の drone を止める


def test_swoosh_row_for_every_tempo():
    seen = set()
    for s in range(1, 80):
        song, plan = build(s)
        if plan.bpm in seen:
            continue
        seen.add(plan.bpm)
        pat = song.patterns[4]
        sw = [r for r in range(64) if pat.get(r, 0).sample == sc.SWOOSH][0]
        assert sw - 48 == 16 - round(0.9 / (15 / plan.bpm)) and sw - 48 in (7, 8)
    assert seen == set(profile.tempo_choices)


@pytest.mark.parametrize("seed", SEEDS)
def test_arp_and_registers(seed):
    song, _ = build(seed)
    strings, pizz, lead = (song.samples[i - 1] for i in (sc.STRINGS, sc.PIZZ, sc.LEAD))
    for p, r, ch, c in iter_cells(song):
        if c.note is None:
            continue
        if c.sample == sc.STRINGS:
            assert sc.HARMONY_REG[0] <= c.note + strings.shift <= sc.HARMONY_REG[1]
            assert c.effect != 0 or c.param == 0 or c.note + max(c.param >> 4, c.param & 15) <= 35
        elif c.sample == sc.PIZZ:
            assert sc.PIZZ_REG[0] <= c.note + pizz.shift <= sc.PIZZ_REG[1]
        elif c.sample == sc.LEAD:
            assert sc.LEAD_REG[0] <= c.note + lead.shift <= sc.LEAD_REG[1]
        elif c.sample == sc.DRONE:
            assert 0 <= c.note - 24 <= 11


def test_deterministic_and_seed_sensitive_and_streams_independent():
    assert serialize(build(9)[0]) == serialize(build(9)[0]) != serialize(build(10)[0])

    class Perturbed(type(profile)):
        def begin_pattern(self, pctx, rng):
            rng.drums.random()
            return super().begin_pattern(pctx, rng)

    for seed in (1, 2, 3):
        base, pert = engine.build_song(profile, seed), engine.build_song(Perturbed(), seed)
        for idx in (3, 4):                                   # b / climax の lead（melody ストリームのみ）
            for r in range(64):
                assert base.patterns[idx].get(r, 3) == pert.patterns[idx].get(r, 3)


def test_generate_writes_verified_file(tmp_path):
    res = engine.generate(profile, 8, tmp_path / "c.mod")
    assert res.issues == [] and res.path.stat().st_size < 200_000
