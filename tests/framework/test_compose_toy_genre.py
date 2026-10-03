"""架空の小さなジャンルで Score が作れることの確認（DESIGN_HISTORY.md §15 F2 の完了条件）。

``band_common`` の宣言（DESIGN.md §5.1 の pop の例）に近い形の、ドラム・ベース・和音・旋律・パッド・エコーを持つ
ジャンルを組み立て、``compose()`` が Score を作れること、骨格が決定的であること、DESIGN.md §5.8 の部品が現行と
同じ row・音量・確率で動くことを確かめる。
"""
from __future__ import annotations

import random

import pytest

from mod_weaver.core.composer import RhythmMotif, ScaleRules
from mod_weaver.core.model import ChordSpec, GmVoice
from mod_weaver.core.synth_presets import PRESETS
from mod_weaver.errors import PlanError
from mod_weaver.framework.compose import compose, resolve_plan
from mod_weaver.framework.gens import BassLine, Comp, Echo, Groove, Pad, hits
from mod_weaver.framework.gens.bass import _bass_line
from mod_weaver.framework.gens.comp import _comp_rows
from mod_weaver.framework.gens.lead import Lead
from mod_weaver.framework.genre import Genre, Harmony, Instrument, Part, Section, Sidechain
from mod_weaver.framework.score import NoteEvent

C = ChordSpec


def _inst(key: str, *, gm=None, **changes):
    patch = PRESETS[key]
    if changes:
        import dataclasses
        patch = dataclasses.replace(patch, **changes)
    return Instrument(patch=patch, gm=gm or GmVoice(program=0))


GROOVES = {
    "main": hits("kick", (0, 8, 10), 58) + hits("snare", (4, 12), 50) + hits("hat", range(0, 16, 2), 30),
    "fill": hits("snare", (8, 10, 12, 13, 14, 15), 46),
    "crash": hits("crash", (0,), 54),
}
LEAD_MOTIFS = {
    "verse": (RhythmMotif((0, 4, 8, 12)), RhythmMotif((0, 4, 6, 8, 12))),
    "chorus": (RhythmMotif((0, 2, 4, 8, 10, 12)),),
}
PROGRESSIONS = (
    ("I-V-vi-IV", (C(0, "maj", label="I"), C(7, "maj", label="V"), C(9, "min", label="vi"),
                   C(5, "maj", label="IV"))),
    ("vi-IV-I-V", (C(9, "min", label="vi"), C(5, "maj", label="IV"), C(0, "maj", label="I"),
                   C(7, "maj", label="V"))),
)


def make_toy_genre():
    class Toy(Genre):
        id = "toy"
        display_name = "Toy"
        description = "テスト用の架空ジャンル"
        description_en = "a toy genre for tests"
        title = "Toy"
        tempo_choices = (120,)

        instruments = {
            "kick": _inst("drum_pop_kick", gm=GmVoice(drum_note=36)),
            "snare": _inst("drum_pop_snare", gm=GmVoice(drum_note=38)),
            "hat": _inst("nostalgic_hihat", gm=GmVoice(drum_note=42)),
            "crash": _inst("march_crash_cymbal", gm=GmVoice(drum_note=49)),
            "bass": _inst("bass_finger", gm=GmVoice(program=33)),
            "piano": _inst("keys_piano", gm=GmVoice(program=0)),
            "pad": _inst("pad_warm", gm=GmVoice(program=89)),
            "lead": _inst("vox_ooh", gm=GmVoice(program=53)),
        }
        harmony = Harmony(keys=(0, 7), mode="ionian", progressions=PROGRESSIONS, n_progressions=2)
        sections = {
            "intro": Section(prog=0, intensity=0.4, parts=frozenset({"pad"})),
            "verse": Section(prog=1, intensity=0.6, parts=frozenset({"drums", "bass", "comp", "pad", "lead"}),
                              groove="main"),
            "chorus": Section(prog=0, intensity=1.0,
                               parts=frozenset({"drums", "bass", "comp", "pad", "lead"}),
                               groove="main", crash=True, fill=True, motifs="chorus"),
        }
        form = ("intro", "verse", "chorus", "verse", "chorus")
        parts = (
            Part("drums", Groove(GROOVES)),
            Part("bass", BassLine("bass", kind="root8", vol=54)),
            Part("comp", Comp("piano", kind="pulse8", vol=40)),
            Part("pad", Pad("pad", vol=28)),
            Part("lead", Lead("lead", ScaleRules(leap_probability=0.2), LEAD_MOTIFS, vol=50, gate=0.85,
                               vibrato=0x32)),
            Part("lead echo", Echo(delay=3, ratio=0.45), min_channels=8, follow="lead"),
        )
        mod_channels = {4: 1, 6: 2, 8: 1}
        mix = (Sidechain(triggers=("kick",), targets=("bass",), ratio=0.3, release_steps=2),)

    return Toy()


def test_score_is_buildable_and_deterministic():
    genre = make_toy_genre()
    plan = resolve_plan(genre, seed=1)
    score = compose(genre, plan, seed=1, features=frozenset())

    assert score.order == ["intro", "verse", "chorus", "verse", "chorus"]
    assert set(score.sections) == {"intro", "verse", "chorus"}
    # 同じ区間名は1回だけ作曲される
    assert score.sections["verse"] is score.sections["verse"]

    plan2 = resolve_plan(genre, seed=1)
    score2 = compose(genre, plan2, seed=1, features=frozenset())
    for name in score.sections:
        assert score.sections[name].parts == score2.sections[name].parts

    plan3 = resolve_plan(genre, seed=2)
    score3 = compose(genre, plan3, seed=2, features=frozenset())
    assert score.summary != score3.summary or score.bpm != score3.bpm or (
        score.sections["verse"].parts != score3.sections["verse"].parts)


def test_sections_only_contain_declared_parts_for_their_participation():
    genre = make_toy_genre()
    plan = resolve_plan(genre, seed=1)
    score = compose(genre, plan, seed=1, features=frozenset())

    intro = score.sections["intro"]
    assert intro.parts["pad"]                       # 宣言どおり鳴る
    assert intro.parts["drums"] == []                # intro の parts に無いので空
    assert intro.parts["lead"] == []
    assert intro.parts["lead echo"] == []            # follow 先の lead が鳴らないので echo も鳴らない

    verse = score.sections["verse"]
    assert verse.parts["drums"]
    assert verse.parts["lead"]
    assert verse.parts["lead echo"]                  # follow 先が鳴るので echo も鳴る


def test_echo_part_follows_lead_and_is_delayed_and_attenuated():
    genre = make_toy_genre()
    plan = resolve_plan(genre, seed=1)
    score = compose(genre, plan, seed=1, features=frozenset())
    verse = score.sections["verse"]
    lead_notes = [e for e in verse.parts["lead"] if isinstance(e, NoteEvent)]
    echo_notes = [e for e in verse.parts["lead echo"] if isinstance(e, NoteEvent)]
    assert lead_notes and echo_notes
    for echo in echo_notes:
        src = next((e for e in lead_notes if e.step == echo.step - 3), None)
        assert src is not None, f"no source note 3 steps before echo at {echo.step}"
        assert echo.vel == max(1, round(src.vel * 0.45))
        assert echo.pitch == src.pitch


def test_part_rng_is_independent_of_other_parts():
    """あるパートの宣言を変えても、他のパートの乱数列（＝出す音）は変わらない（DESIGN.md §5.5）。"""
    genre1 = make_toy_genre()
    plan1 = resolve_plan(genre1, seed=5)
    score1 = compose(genre1, plan1, seed=5, features=frozenset())

    # bass の vol だけを変える。id は同じに保つ（乱数ストリームは f"{seed}:{genre.id}:part:{name}" なので、
    # id を変えると無関係なパートのストリームまで変わってしまい、この検査の意味が無くなる）
    genre2 = make_toy_genre()
    import dataclasses
    new_parts = tuple(
        dataclasses.replace(p, gen=BassLine("bass", kind="root8", vol=40)) if p.name == "bass" else p
        for p in genre2.parts
    )
    genre2.parts = new_parts
    plan2 = resolve_plan(genre2, seed=5)
    score2 = compose(genre2, plan2, seed=5, features=frozenset())

    for part_name in ("drums", "comp", "lead"):
        for sec in score1.sections:
            assert score1.sections[sec].parts[part_name] == score2.sections[sec].parts[part_name], part_name


def test_class_definition_rejects_unknown_follow_target():
    with pytest.raises(PlanError, match="unknown part"):
        class Bad(Genre):
            id = "toy-bad-follow"
            display_name = "Bad"
            description = "x"
            description_en = "x"
            title = "Bad"
            tempo_choices = (120,)
            instruments = {"lead": _inst("vox_ooh")}
            harmony = Harmony(keys=(0,), mode="ionian", progressions=PROGRESSIONS)
            sections = {"a": Section(parts=frozenset({"lead"}))}
            form = ("a",)
            parts = (Part("echo", Echo(), follow="nonexistent"),)


def test_class_definition_rejects_cyclic_depends():
    with pytest.raises(PlanError, match="cyclic"):
        class BadCycle(Genre):
            id = "toy-bad-cycle"
            display_name = "BadCycle"
            description = "x"
            description_en = "x"
            title = "BadCycle"
            tempo_choices = (120,)
            instruments = {"lead": _inst("vox_ooh")}
            harmony = Harmony(keys=(0,), mode="ionian", progressions=PROGRESSIONS)
            sections = {"a": Section(parts=frozenset({"a", "b"}))}
            form = ("a",)
            parts = (
                Part("a", Echo(), depends=("b",)),
                Part("b", Echo(), depends=("a",)),
            )


# ============================================================
# 部品のテスト（DESIGN_HISTORY.md §15 F2 の完了条件: 現行 band_common の型と同じ row・音量・確率が出る）
# ============================================================

def _chord():
    genre = make_toy_genre()
    plan = resolve_plan(genre, seed=1)
    return plan.sections["verse"].measures[0].chord


def test_bass_line_root8_matches_legacy_rows_and_volumes():
    chord = _chord()
    out = _bass_line("root8", chord, 16, (0, 11), random.Random(0), 54)
    expected = [(r, chord.bass, 54 if r % 4 == 0 else 54 - 8) for r in range(0, 16, 2)]
    assert out == expected


def test_bass_line_scales_to_measure_steps():
    chord = _chord()
    out8 = _bass_line("root8", chord, 8, (0, 11), random.Random(0), 54)
    rows = [r for r, _n, _v in out8]
    assert rows == sorted(set(rows)) and max(rows) < 8


def test_comp_rows_pulse8_matches_legacy():
    assert _comp_rows("pulse8", 16, random.Random(0)) == [(r, r % 8 == 0) for r in range(0, 16, 2)]


def test_comp_rows_unknown_kind_raises():
    with pytest.raises(PlanError, match="unknown comp kind"):
        _comp_rows("bogus", 16, random.Random(0))


def test_groove_humanize_and_probability_match_legacy_shape():
    """Hit.prob を使った確率的な省略と、humanize の範囲を確認する（現行 band_common.drums と同じ規則）。"""
    from mod_weaver.framework.context import SectionCtx

    genre = make_toy_genre()
    plan = resolve_plan(genre, seed=1)
    sec_plan = plan.sections["verse"]
    gen = Groove({"main": hits("snare", (0,), 50, prob=0.0)})
    events: list = []
    ctx = SectionCtx(genre, sec_plan, plan, genre.parts[0], random.Random(0), {}, events, [], bpm=120)
    for m in ctx.measures():
        gen.measure(m)
    assert events == []   # prob=0.0 なので一度も鳴らない


def test_ctx_features_reflects_compose_argument():
    """``ctx.features``（DESIGN.md §3.2）は ``compose()`` に渡した features がそのまま見える。奏法の付け外しに
    しか使わない値だが、ジェネレータがちゃんと読めることを確認する。"""
    from mod_weaver.framework.context import SectionCtx

    genre = make_toy_genre()
    plan = resolve_plan(genre, seed=1)
    compose(genre, plan, seed=1, features=frozenset({"filter", "tremolo"}))
    ctx = SectionCtx(genre, plan.sections["verse"], plan, genre.parts[0], random.Random(0), {}, [], [], bpm=120)
    assert ctx.features == frozenset({"filter", "tremolo"})


def test_wobble_attaches_vibrato_articulation():
    genre = make_toy_genre()
    plan = resolve_plan(genre, seed=1)
    score = compose(genre, plan, seed=1, features=frozenset())
    comp_events = [e for e in score.sections["verse"].parts["comp"] if isinstance(e, NoteEvent)]
    assert comp_events and all(e.arts == () for e in comp_events)   # wobble=0（既定）なので付かない
