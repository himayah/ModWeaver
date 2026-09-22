"""suspense-slow の文法・音域・契約（設計書 §8.3、§11.3）。"""
from __future__ import annotations

import pytest

from mod_weaver import engine
from mod_weaver.core import pitch
from mod_weaver.core.model import Cell
from mod_weaver.core.verify import verify
from mod_weaver.core.writer import serialize
from mod_weaver.profiles import get_profile
from mod_weaver.profiles import suspense_common as sc
from tests.helpers import iter_cells

profile = get_profile("suspense-slow")
SEEDS = list(range(1, 31))
NOTE_ROWS = 16


def build(seed):
    return engine.compose_song(profile, seed)


def test_declaration_and_alias():
    assert profile.id == "suspense-slow" and get_profile("suspense").id == "suspense-slow"
    assert profile.tempo_choices == (64, 66, 68, 70, 72) and profile.rows_per_measure == 16
    assert profile.title == "Suspense Slow" and profile.default_filename == "SuspenseSlow.mod"
    assert (profile.tempo_policy, profile.rng_mode, profile.strict_buffers) == ("engine", "streams", True)


@pytest.mark.parametrize("seed", SEEDS)
def test_structure_and_clean_verification(seed):
    song, plan = build(seed)
    assert plan.order == [0, 1, 2, 1, 3, 4] and len(song.patterns) == 5
    assert [p.kind for p in plan.patterns] == ["hush", "pedal", "phrygian", "shock", "aftermath"]
    assert plan.bpm in profile.tempo_choices and len(song.samples) == 7
    issues = verify(serialize(song), profile.channel_plan)
    assert issues == []                                    # ERROR/WARN/INFO いずれも無し（V15・V16 を含む）
    a, b = plan.patterns[1].slots, plan.patterns[2].slots
    assert [s.chord.label for s in a] == [s.chord.label for s in plan.patterns[0].slots] == [s.chord.label for s in plan.patterns[4].slots]
    assert [s.chord.label for s in a] != [s.chord.label for s in b]        # A と B は別進行
    assert [s.chord.label for s in b] == [s.chord.label for s in plan.patterns[3].slots]


def test_tempo_cell_is_on_first_empty_channel_of_first_pattern():
    song, plan = build(1)
    assert song.patterns[0].get(0, 0) == Cell(None, 0, 0x0F, plan.bpm)


@pytest.mark.parametrize("seed", SEEDS)
def test_every_shock_hit_has_guard_before_it(seed):
    """anvil の直前 8 row に heart / pizz / lead の発音がない（swoosh は許可）。"""
    song, _ = build(seed)
    guarded = {sc.HEART, sc.PIZZ, sc.LEAD}
    for p, pat in enumerate(song.patterns):
        for r in range(pat.rows):
            if pat.get(r, sc.CH_FX).sample == sc.ANVIL:
                for rr in range(max(0, r - sc.SHOCK_GUARD_ROWS), r):
                    for ch in range(4):
                        c = pat.get(rr, ch)
                        assert not (c.note is not None and c.sample in guarded), (seed, p, r, rr, ch)


@pytest.mark.parametrize("seed", SEEDS)
def test_shock_pattern_grammar(seed):
    song, plan = build(seed)
    pat, bpm = song.patterns[3], plan.bpm
    # m1: 全 16 row に新規 note なし。持続音は row 0 で消音
    for r in range(16, 32):
        assert all(pat.get(r, c).note is None for c in range(4))
    assert [pat.get(16, c) for c in (1, 2, 3)] == [Cell(None, 0, vol=0)] * 3
    # m2: swoosh が「rows_per_measure − round(0.9/row_sec)」に置かれる
    sw = [r for r in range(32, 48) if pat.get(r, 0).sample == sc.SWOOSH]
    assert sw == [32 + 16 - round(0.9 / (15 / bpm))] == [44]
    # m3: row 0 に anvil vol 64、drone vol 50、lead 高音＋ビブラート
    anvil = pat.get(48, 0)
    assert anvil.sample == sc.ANVIL and anvil.vol == 64 and anvil.note == 35   # B-3 で発音（unpitched）
    assert pat.get(48, 1).vol == 50 and pat.get(48, 1).sample == sc.DRONE
    lead = pat.get(48, 3)
    assert lead.sample == sc.LEAD and (lead.effect, lead.param) == (4, 0x46) and lead.vol is None
    # pizz ostinato: row 2,4,…,14 の vol が単調非減少で 30→60、同一音
    ost = [pat.get(48 + r, 2) for r in range(2, 16, 2)]
    assert [c.vol for c in ost] == sorted(c.vol for c in ost) and ost[0].vol == 30 and ost[-1].vol == 60
    assert len({c.note for c in ost}) == 1 and all(c.sample == sc.PIZZ for c in ost)
    assert sc.PIZZ_REG[0] <= ost[0].note <= sc.PIZZ_REG[1]
    # m0: 心拍加速 40→56
    lubs = [pat.get(r, 0).vol for r in (0, 4, 8, 12)]
    assert lubs[0] == 40 and lubs[-1] == 56 and lubs == sorted(lubs)


@pytest.mark.parametrize("seed", SEEDS)
def test_drone_follows_chord_bass_and_pedal_is_logical_zero(seed):
    song, plan = build(seed)
    drone = song.samples[sc.DRONE - 1]
    for p, pat in enumerate(song.patterns):
        slots = plan.patterns[p].slots
        for m in range(4):
            c = pat.get(m * 16, sc.CH_LOW)
            if c.note is not None:
                logical = c.note + drone.shift
                assert logical == slots[m].chord.bass
                if slots[m].chord.label in ("Cdim", "Db/C", "B/C"):    # pedal 進行
                    assert logical == 0 and c.note == 24
                assert 0 <= logical <= 11


@pytest.mark.parametrize("seed", SEEDS)
def test_strings_root_in_harmony_register_and_arp_in_range(seed):
    song, plan = build(seed)
    strings = song.samples[sc.STRINGS - 1]
    seen = 0
    for p, r, ch, c in iter_cells(song):
        if c.sample == sc.STRINGS and c.note is not None:
            logical = c.note + strings.shift
            assert sc.HARMONY_REG[0] <= logical <= sc.HARMONY_REG[1]
            if c.has_effect:
                assert c.effect == 0 and c.note + max(c.param >> 4, c.param & 0xF) <= 35
                assert c.vol is None
            seen += 1
    assert seen > 0


@pytest.mark.parametrize("seed", SEEDS)
def test_lead_notes_in_register_and_articulation(seed):
    song, plan = build(seed)
    lead = song.samples[sc.LEAD - 1]
    pat = song.patterns[2]          # phrygian
    glides = 0
    for m in range(4):
        cells = [(r, pat.get(m * 16 + r, 3)) for r in range(16)]
        notes = [(r, c) for r, c in cells if c.note is not None]
        assert 1 <= len(notes) <= 2
        for r, c in notes:
            assert sc.LEAD_REG[0] <= c.note + lead.shift <= sc.LEAD_REG[1]
        offs = [r for r, c in cells if c == Cell(None, 0, vol=0)]
        closing = [15] if m == 3 else []             # pattern 末（row 63）の消音は finalize が追加
        if len(notes) == 1:
            assert notes[0][0] == 0 and notes[0][1].vol is not None
            assert offs == [14] + closing                                                # gate 0.9 → row 14
        else:
            (r2, c2) = notes[1]
            assert r2 == 8 and (c2.effect, c2.param) == (3, 0x0A) and c2.vol is None and c2.sample == sc.LEAD
            assert offs == [15]
            glides += 1
    assert pat.get(63, 3) == Cell(None, 0, vol=0)
    assert song.patterns[3].get(63, 3) == Cell(None, 0, vol=0)    # shock 末で lead を消音


def test_glide_appears_in_some_seed():
    assert any(
        song.patterns[2].get(m * 16 + 8, 3).effect == 3
        for song, _ in (build(s) for s in SEEDS) for m in range(4)
    )


@pytest.mark.parametrize("seed", SEEDS[:10])
def test_pedal_pattern_dropout_and_optional_shock(seed):
    song, plan = build(seed)
    pat = song.patterns[1]
    drop = [m for m in range(4) if pat.get(m * 16, 1) == Cell(None, 0, vol=0)]
    assert len(drop) == 1 and drop[0] in (1, 2)
    d = drop[0]
    assert pat.get(d * 16, 2) == Cell(None, 0, vol=0)
    for r in range(d * 16 + 1, d * 16 + 16):                 # dropout measure に心拍なし
        assert pat.get(r, 0).is_empty
    anvils = [r for r in range(64) if pat.get(r, 0).sample == sc.ANVIL]
    assert anvils in ([], [(d + 1) * 16])


def test_pedal_pattern_variants_are_all_reachable():
    """dropout 位置・anvil 有無・pizz スタブ有無が seed で変化する。"""
    seen = set()
    for s in range(1, 60):
        pat = build(s)[0].patterns[1]
        d = 1 if pat.get(16, 1) == Cell(None, 0, vol=0) else 2
        anvil = any(pat.get(r, 0).sample == sc.ANVIL for r in range(64))
        stab = pat.get(40, 3).sample == sc.PIZZ
        seen.add((d, anvil, stab))
    assert len(seen) >= 6


def test_stab_is_suppressed_when_inside_shock_guard():
    """dropout=m2 かつ anvil あり（anvil row 48）なら、row 40 のスタブは置かれない。"""
    hit = False
    for s in range(1, 200):
        pat = build(s)[0].patterns[1]
        if pat.get(48, 0).sample == sc.ANVIL:
            hit = True
            assert pat.get(40, 3).is_empty
    assert hit


def test_hush_and_aftermath_fade_shapes():
    song, _ = build(4)
    hush = song.patterns[0]
    assert [hush.get(m * 16, 2).vol for m in range(4)] == [6, 14, 22, 30]
    assert all(hush.get(r, 0).sample != sc.HEART for r in range(32) if r != 0)      # m0,m1 に心拍なし
    lubs = [hush.get(r, 0).vol for r in range(32, 64, 4)]
    assert lubs[0] == 26 and lubs[-1] == 40 and lubs == sorted(lubs)
    after = song.patterns[4]
    assert [after.get(m * 16, 1).vol for m in range(4)] == [40, 27, 13, 0]
    assert [after.get(m * 16, 2).vol for m in range(4)] == [34, 25, 17, 8]
    heart = [after.get(r, 0) for r in range(64) if after.get(r, 0).sample == sc.HEART]
    lub = [c.vol for c in heart if c.vol >= 10][:7]
    assert after.get(48, 0).vol == 10 and all(after.get(r, 0).is_empty for r in range(49, 64))   # 最終 measure は lub のみ
    assert lub[0] == 30


def test_deterministic_and_seed_sensitive():
    assert serialize(build(11)[0]) == serialize(build(11)[0])
    assert serialize(build(11)[0]) != serialize(build(12)[0])


def test_rng_streams_are_independent_between_parts():
    """drums ストリームの消費を変えても、melody ストリームだけで決まる lead は変わらない（D9）。"""
    class Perturbed(type(profile)):
        def begin_pattern(self, pctx, rng):
            rng.drums.random()                      # drums を余計に消費
            return super().begin_pattern(pctx, rng)

    perturbed_somewhere = False
    for seed in range(1, 13):
        base = engine.build_song(profile, seed)
        pert = engine.build_song(Perturbed(), seed)
        perturbed_somewhere |= serialize(base) != serialize(pert)     # 摂動が効く seed がある
        for r in range(64):                                           # phrygian pattern の lead は不変
            assert base.patterns[2].get(r, 3) == pert.patterns[2].get(r, 3)
    assert perturbed_somewhere


def test_generate_writes_verified_file(tmp_path):
    out = tmp_path / "s.mod"
    res = engine.generate(profile, 5, out)
    assert res.issues == [] and out.stat().st_size < 200_000
    assert out.read_bytes() == serialize(engine.build_song(profile, 5))
