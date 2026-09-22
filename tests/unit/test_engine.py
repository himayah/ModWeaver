from __future__ import annotations

import pytest

from mod_weaver import engine
from mod_weaver.core.model import Cell, ChordSlot, PatternPlan, SampleSpec, SongPlan, Song, Pattern
from mod_weaver.errors import (
    ChannelConflictError, OutputError, PlanError, SampleConstraintError, VerificationError,
)
from tests.helpers import DUMMY_CHORD, make_profile, tone


def test_build_song_basic_structure():
    song = engine.build_song(make_profile(), 1)
    assert song.title == "Dummy" and song.order == [0] and len(song.patterns) == 1
    assert [s.name for s in song.samples] == ["One", "Two"]
    pat = song.patterns[0]
    for m in range(4):                                  # 各 measure の row 4 に blit されている
        assert pat.get(m * 16 + 4, 1).sample == 2


# ---------------- apply_tempo ----------------

def test_tempo_goes_to_lowest_empty_channel():
    song = engine.build_song(make_profile(row0_cells={0: Cell(24, 1, vol=30)}), 1)
    assert song.patterns[0].get(0, 1) == Cell(None, 0, 0x0F, 100)
    assert song.patterns[0].get(0, 0) == Cell(24, 1, vol=30)


def test_tempo_uses_note_only_channel_when_no_empty():
    cells = {0: Cell(24, 1, vol=30), 1: Cell(20, 2, vol=30), 2: Cell(20, 1, 0, 0x47), 3: Cell(20, 2)}
    song = engine.build_song(make_profile(row0_cells=cells), 1)
    assert song.patterns[0].get(0, 3) == Cell(20, 2, 0x0F, 100)      # vol/effect 無しの note セルのみ


def test_tempo_conflict_when_no_slot():
    cells = {0: Cell(24, 1, vol=30), 1: Cell(20, 2, vol=30), 2: Cell(20, 1, 0, 0x47), 3: Cell(20, 2, vol=3)}
    with pytest.raises(ChannelConflictError):
        engine.build_song(make_profile(row0_cells=cells), 1)


def test_tempo_policy_profile_does_nothing():
    song = engine.build_song(make_profile(tempo_policy="profile"), 1)
    assert all(song.patterns[0].get(0, c).is_empty for c in range(4))


# ---------------- 契約検査 ----------------

def test_plan_bpm_not_in_choices():
    with pytest.raises(PlanError, match="tempo_choices"):
        engine.build_song(make_profile(bpm=101), 1)


def test_plan_rows_mismatch():
    with pytest.raises(PlanError, match="slots cover"):
        engine.build_song(make_profile(n_measures=3), 1)


@pytest.mark.parametrize("order", [[], [1], [-1], [0] * 129])
def test_plan_order_invalid(order):
    with pytest.raises(PlanError):
        engine.build_song(make_profile(order=order), 1)


def test_plan_no_patterns_and_zero_measure_slot():
    class NoPat(make_profile().__class__):
        def plan(self, rng):
            return SongPlan(100, [], [0])

    with pytest.raises(PlanError, match="no patterns"):
        engine.build_song(NoPat(), 1)

    class ZeroSlot(make_profile().__class__):
        def plan(self, rng):
            return SongPlan(100, [PatternPlan("a", [ChordSlot(DUMMY_CHORD, 0)] + [ChordSlot(DUMMY_CHORD, 4)])], [0])

    with pytest.raises(PlanError):
        engine.build_song(ZeroSlot(), 1)


def test_plan_too_many_patterns():
    class Many(make_profile().__class__):
        def plan(self, rng):
            slots = [ChordSlot(DUMMY_CHORD, 4)]
            return SongPlan(100, [PatternPlan("a", list(slots)) for _ in range(65)], [64])

    with pytest.raises(PlanError, match="too many patterns"):
        engine.build_song(Many(), 1)


@pytest.mark.parametrize("attrs", [
    dict(rows_per_measure=7), dict(rows_per_measure=0), dict(channel_plan=()), dict(tempo_policy="x"),
    dict(rng_mode="x"), dict(target_format="xm"), dict(title="x" * 21), dict(title="日本"),
])
def test_profile_declaration_errors(attrs):
    with pytest.raises(PlanError):
        engine.build_song(make_profile(**attrs), 1)


def test_rows_per_measure_8_is_accepted():
    prof = make_profile(rows_per_measure=8, n_measures=8, tempo_policy="profile")
    song = engine.build_song(prof, 1)
    assert song.patterns[0].get(60, 1).sample == 2


def test_sample_constraints_and_count():
    class Bad(make_profile().__class__):
        def build_samples(self):
            return {"x": SampleSpec("X", b"abc", 10)}

    with pytest.raises(SampleConstraintError):
        engine.build_song(Bad(), 1)

    class TooMany(make_profile().__class__):
        def build_samples(self):
            return {f"s{i}": SampleSpec("S", tone(), 10) for i in range(32)}

    with pytest.raises(SampleConstraintError, match="too many"):
        engine.build_song(TooMany(), 1)


def test_disallowed_sample_raises_during_compose():
    class Bad(make_profile().__class__):
        def compose_measure(self, mctx, state, rng, buf):
            buf.put(0, 0, mctx.instruments["two"].cell(20))     # ch1 は sample 1 のみ許可

    with pytest.raises(ChannelConflictError):
        engine.build_song(Bad(), 1)


# ---------------- 乱数 ----------------

def test_rng_modes_pass_expected_types():
    import random
    from mod_weaver.core.model import RngStreams
    seen = []

    class Spy(make_profile().__class__):
        def plan(self, rng):
            seen.append(type(rng))
            return super().plan(rng)

    engine.build_song(Spy(), 1)
    engine.build_song(type("S2", (Spy,), {"rng_mode": "single"})(), 1)
    assert seen == [RngStreams, random.Random]


def test_hook_call_order_and_state_passing():
    calls = []

    class Trace(make_profile().__class__):
        def begin_pattern(self, pctx, rng):
            calls.append(("begin", pctx.index, pctx.is_first_in_order, pctx.kind))
            return {"n": 0}

        def compose_measure(self, mctx, state, rng, buf):
            state["n"] += 1
            calls.append(("measure", mctx.measure_idx, mctx.is_last, mctx.n_measures))

        def finalize_pattern(self, pctx, pattern, state, rng):
            calls.append(("final", state["n"]))

    engine.build_song(Trace(), 1)
    assert calls == [
        ("begin", 0, True, "a"), ("measure", 0, False, 4), ("measure", 1, False, 4),
        ("measure", 2, False, 4), ("measure", 3, True, 4), ("final", 4),
    ]


def test_multi_measure_slot_offsets():
    offs = []

    class Multi(make_profile().__class__):
        def plan(self, rng):
            return SongPlan(100, [PatternPlan("a", [ChordSlot(DUMMY_CHORD, 3), ChordSlot(DUMMY_CHORD, 1)])], [0])

        def compose_measure(self, mctx, state, rng, buf):
            offs.append(mctx.chord_measure_offset)

    engine.build_song(Multi(), 1)
    assert offs == [0, 1, 2, 0]


def test_post_processors_run_before_tempo():
    seen = {}

    def post(song, plan):
        seen["tempo_present"] = any(not c.is_empty for c in [song.patterns[0].get(0, ch) for ch in range(4)])
        song.patterns[0].replace(10, 0, Cell(24, 1, vol=10))

    song = engine.build_song(make_profile(post_processors=(post,)), 1)
    assert seen["tempo_present"] is False and song.patterns[0].get(10, 0) == Cell(24, 1, vol=10)
    assert song.patterns[0].get(0, 0) == Cell(None, 0, 0x0F, 100)


# ---------------- generate ----------------

def test_generate_writes_file_and_returns_result(tmp_path):
    out = tmp_path / "d.mod"
    res = engine.generate(make_profile(), 5, out)
    assert out.exists() and res.path == out and res.seed == 5 and res.plan.bpm == 100
    assert not [i for i in res.issues if i.level == "ERROR"]


def test_generate_seed_none_uses_default_range(tmp_path):
    res = engine.generate(make_profile(), None, tmp_path / "d.mod")
    assert 100000 <= res.seed <= 999999


def test_generate_verification_error_writes_nothing(tmp_path):
    out = tmp_path / "bad.mod"

    def post(song, plan):
        song.patterns[0].replace(20, 1, Cell(29, 2, 0, 0x47))   # V16: t+7 > 35

    with pytest.raises(VerificationError) as ei:
        engine.generate(make_profile(post_processors=(post,)), 1, out)
    assert any(i.code == "V16" for i in ei.value.issues)
    assert not out.exists() and list(tmp_path.iterdir()) == []


def test_generate_skip_verify(tmp_path):
    def post(song, plan):
        song.patterns[0].replace(20, 1, Cell(29, 2, 0, 0x47))

    res = engine.generate(make_profile(post_processors=(post,)), 1, tmp_path / "x.mod", verify=False)
    assert res.issues == [] and res.path.exists()


def test_generate_logs_warnings(tmp_path, caplog, monkeypatch):
    import logging
    # cli.main が propagate=False にするため、他テストの実行順に依存しないよう戻す
    monkeypatch.setattr(logging.getLogger("mod_weaver"), "propagate", True)

    def post(song, plan):
        for r in range(5):
            song.patterns[0].replace(r + 30, 0, Cell(24, 1, vol=64))
            song.patterns[0].replace(r + 30, 3, Cell(24, 2, vol=64))    # 左 128 → V15

    with caplog.at_level(logging.WARNING, logger="mod_weaver"):
        res = engine.generate(make_profile(post_processors=(post,)), 1, tmp_path / "x.mod")
    assert any(i.code == "V15" for i in res.issues)
    assert any("V15" in r.message for r in caplog.records)


def test_generate_output_error(tmp_path):
    with pytest.raises(OutputError):
        engine.generate(make_profile(), 1, tmp_path / "nodir" / "x.mod")


def test_verification_error_message_summarises():
    from mod_weaver.core.verify import Issue
    e = VerificationError([Issue("ERROR", f"V0{i}", "m") for i in range(1, 8)])
    assert "V01" in str(e) and "+2 more" in str(e)
