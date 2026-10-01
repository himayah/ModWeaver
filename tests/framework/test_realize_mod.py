"""TrackerRealizer（MOD）の確認（FRAMEWORK_REDESIGN.md §16.2 F3 の完了条件）。

lane の需要・ladder（§9.3）・サンプル計画（§8.4）・セル化（§9.6〜§9.7）・サイドチェイン（§9.8）・
pattern への分割（§9.9）を、kit・和音・double・sidechain を持つ小さな架空ジャンルで確認する。
最後に ``core.formats.get_format("mod")`` の serialize/verify を実際に通す。
"""
from __future__ import annotations

from mod_weaver.core.composer import RhythmMotif, ScaleRules
from mod_weaver.core.formats import get_format
from mod_weaver.core.model import ChordSpec, GmVoice
from mod_weaver.core.synth_presets import PRESETS
from mod_weaver.framework.compose import compose, resolve_plan
from mod_weaver.framework.gens import BassLine, Comp, Groove, hits
from mod_weaver.framework.gens.lead import Lead
from mod_weaver.framework.genre import Double, Genre, Harmony, Instrument, Kit, Part, Section, Sidechain
from mod_weaver.framework.realize import lanes as lanesmod
from mod_weaver.framework.realize.tracker import realize_mod
from mod_weaver.framework.score import NoteEvent
from mod_weaver.framework.target import resolve as resolve_target

C = ChordSpec


def _inst(key: str, *, gm=None):
    return Instrument(patch=PRESETS[key], gm=gm or GmVoice(program=0))


GROOVES = {
    "main": hits("kick", (0, 8, 10), 58) + hits("snare", (4, 12), 50) + hits("hat", range(0, 16, 2), 30),
}
LEAD_MOTIFS = {"verse": (RhythmMotif((0, 4, 8, 12)),)}
PROGRESSIONS = (("I", (C(0, "maj", label="I"),)),)


def make_genre():
    class RealizeToy(Genre):
        id = "realize-toy"
        display_name = "RealizeToy"
        description = "x"
        description_en = "x"
        title = "RealizeToy"
        tempo_choices = (120,)

        instruments = {
            "kick": _inst("drum_pop_kick", gm=GmVoice(drum_note=36)),
            "snare": _inst("drum_pop_snare", gm=GmVoice(drum_note=38)),
            "hat": _inst("nostalgic_hihat", gm=GmVoice(drum_note=42)),
            "bass": _inst("bass_finger", gm=GmVoice(program=33)),
            "piano": _inst("keys_piano", gm=GmVoice(program=0)),
            "lead": _inst("vox_ooh", gm=GmVoice(program=53)),
        }
        harmony = Harmony(keys=(0,), mode="ionian", progressions=PROGRESSIONS, n_progressions=1, fixed=True)
        sections = {"a": Section(parts=frozenset({"drums", "bass", "comp", "lead"}))}
        form = ("a",)
        parts = (
            Part("drums", Groove(GROOVES),
                 kit=Kit(groups=(("kick_snare", ("kick", "snare")), ("hat", ("hat",))),
                         priority={"snare": 2})),
            Part("bass", BassLine("bass", kind="root8", vol=54), double=Double()),
            Part("comp", Comp("piano", kind="pulse8", vol=40), chord_spread=40),
            Part("lead", Lead("lead", ScaleRules(leap_probability=0.2), LEAD_MOTIFS, vol=50, gate=0.85),
                 min_channels=6),
        )
        mod_channels = {4: 1, 6: 1, 8: 1}
        mix = (Sidechain(triggers=("kick",), targets=("bass",), ratio=0.3, release_steps=2),)

    return RealizeToy()


def _score(genre, seed=1):
    plan = resolve_plan(genre, seed=seed)
    score = compose(genre, plan, seed=seed, features=frozenset())
    return plan, score


# ============================================================
# lane の需要と ladder（§9.3）
# ============================================================

def test_layout_at_4ch_bakes_chord_and_merges_kit():
    genre = make_genre()
    _plan, score = _score(genre)
    layout = lanesmod.compute_layout(genre, score, budget=4)
    assert layout.active_parts == {"drums", "bass", "comp"}   # lead は min_channels=6 で外れる
    assert len(layout.lanes) == 4
    roles = sorted((l.part_name, l.role) for l in layout.lanes)
    assert roles == [("bass", "mono"), ("comp", "chord_baked"), ("drums", "kit"), ("drums", "kit")]


def test_layout_at_6ch_adds_control_channel():
    genre = make_genre()
    _plan, score = _score(genre)
    layout = lanesmod.compute_layout(genre, score, budget=6)
    assert layout.active_parts == {"drums", "bass", "comp", "lead"}
    assert len(layout.lanes) == 6
    assert [l.role for l in layout.lanes].count("control") == 1


def test_layout_at_8ch_keeps_everything_separate():
    genre = make_genre()
    _plan, score = _score(genre)
    layout = lanesmod.compute_layout(genre, score, budget=8)
    assert len(layout.lanes) == 8
    assert [l.role for l in layout.lanes].count("control") == 0
    kit_lanes = [l for l in layout.lanes if l.part_name == "drums"]
    assert len(kit_lanes) == 3     # kick・snare・hat が分かれたまま（L0 で収まるので ladder が動かない）
    comp_lanes = [l for l in layout.lanes if l.part_name == "comp"]
    assert len(comp_lanes) == 3    # 和音の声部のまま（triad: 根音+2音）
    bass_lanes = [l for l in layout.lanes if l.part_name == "bass"]
    assert len(bass_lanes) == 1    # R1 で double が外れてちょうど収まる


def test_channel_order_is_part_declaration_order():
    genre = make_genre()
    _plan, score = _score(genre)
    layout = lanesmod.compute_layout(genre, score, budget=8)
    seen_parts = [l.part_name for l in layout.lanes]
    first_idx = {name: seen_parts.index(name) for name in ("drums", "bass", "comp", "lead")}
    assert first_idx["drums"] < first_idx["bass"] < first_idx["comp"] < first_idx["lead"]


# ============================================================
# realize_mod() の結合テスト
# ============================================================

def test_realize_mod_passes_verify_at_every_budget():
    genre = make_genre()
    plan, score = _score(genre, seed=3)
    fmt = get_format("mod")
    for budget in (4, 6, 8):
        target = resolve_target("mod", budget, genre, seed=3)
        song, opts = realize_mod(genre, score, plan, target)
        assert song.patterns[0].channels == budget
        data = fmt.serialize(song, opts)
        issues = fmt.verify(data)
        errors = [i for i in issues if i.severity == "ERROR"] if issues and hasattr(issues[0], "severity") else \
            [i for i in issues if getattr(i, "code", "").startswith("E")]
        assert not errors, errors


def test_sample_count_matches_used_instruments_and_chord_shapes():
    genre = make_genre()
    plan, score = _score(genre, seed=3)
    target = resolve_target("mod", 4, genre, seed=3)
    song, _opts = realize_mod(genre, score, plan, target)
    # drums(kick,snare,hat) + bass + comp の焼いた和音の形（1つだけのはず、progressions が1つだけなので）
    assert len(song.samples) == 3 + 1 + 1


def test_sidechain_ducks_bass_near_kick_hits():
    genre = make_genre()
    plan, score = _score(genre, seed=3)
    target = resolve_target("mod", 8, genre, seed=3)
    song, _opts = realize_mod(genre, score, plan, target)
    layout = lanesmod.compute_layout(genre, score, budget=8)
    bass_lane = lanesmod.assign_events(genre, layout, score)   # 触れるだけで例外が出ないことも確認
    assert bass_lane is not None

    sec = score.sections["a"]
    kick_steps = {e.step for e in sec.parts["drums"] if isinstance(e, NoteEvent) and e.inst == "kick"}
    assert kick_steps
    bass_lane_idx = layout.lanes_of("bass")[0].index
    pat = song.patterns[0]
    ducked_found = False
    for step in kick_steps:
        if step >= pat.rows:
            continue
        cell = pat.get(step, bass_lane_idx)
        if cell.vol is not None:
            ducked_found = True
    assert ducked_found


# ============================================================
# pattern への分割（§9.9）
# ============================================================

def test_split_into_patterns_short_section_gets_pattern_break():
    from mod_weaver.core.model import Cell, CellGrid
    from mod_weaver.framework.plan import MeasurePlan
    from mod_weaver.framework.realize.tracker import _split_into_patterns

    import types

    measures = tuple(MeasurePlan(index=i, start=i * 8, steps=8, chord=None, quality="maj", chord_offset=0,
                                  next_chord=None) for i in range(4))   # 4 小節 * 8 step = 32 step
    sec_plan = types.SimpleNamespace(name="x", measures=measures)

    grid = CellGrid(rows=32, plan=None, strict=False, channels=4)
    grid.put(0, 0, Cell(24, 1, 0, 0))
    chunks = _split_into_patterns(sec_plan, grid, budget=4)
    assert len(chunks) == 1
    pat, steps = chunks[0]
    assert pat.rows == 64 and steps == (8, 8, 8, 8)
    assert any(pat.get(31, ch).effect == 0x0D for ch in range(4))   # 31 = 最後の実 row


def test_split_into_patterns_long_section_splits_at_measure_boundary():
    from mod_weaver.core.model import CellGrid
    from mod_weaver.framework.plan import MeasurePlan
    from mod_weaver.framework.realize.tracker import _split_into_patterns

    # 5 小節 * 16 step = 80 step（64 を超える）。4 小節目までで 64、5 小節目が次の pattern に出る
    import types

    measures = tuple(MeasurePlan(index=i, start=i * 16, steps=16, chord=None, quality="maj", chord_offset=0,
                                  next_chord=None) for i in range(5))
    sec_plan = types.SimpleNamespace(name="x", measures=measures)

    grid = CellGrid(rows=80, plan=None, strict=False, channels=4)
    chunks = _split_into_patterns(sec_plan, grid, budget=4)
    assert len(chunks) == 2
    assert chunks[0][1] == (16, 16, 16, 16)
    assert chunks[1][1] == (16,)
    assert chunks[0][0].rows == 64 and chunks[1][0].rows == 64
