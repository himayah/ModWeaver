"""``Genre`` のクラス定義時の宣言検査（FRAMEWORK_REDESIGN.md §13.1 I9）。"""
from __future__ import annotations

import pytest

from mod_weaver.core.model import ChordSpec, GmVoice
from mod_weaver.core.synth_presets import PRESETS
from mod_weaver.errors import PlanError
from mod_weaver.framework.gens import Echo, Groove
from mod_weaver.framework.genre import Genre, Harmony, Instrument, Kit, Part, Section, Sidechain

C = ChordSpec
PROGS = (("I", (C(0, "maj", label="I"),)),)


def _inst(key: str) -> Instrument:
    return Instrument(patch=PRESETS[key], gm=GmVoice(program=0))


def _base_kwargs(**over):
    kw = dict(
        display_name="X", description="x", description_en="x", title="X", tempo_choices=(120,),
        instruments={"kick": _inst("drum_pop_kick"), "snare": _inst("drum_pop_snare")},
        harmony=Harmony(keys=(0,), mode="ionian", progressions=PROGS),
        sections={"a": Section(parts=frozenset({"drums"}))}, form=("a",),
    )
    kw.update(over)
    return kw


def test_mod_channels_must_be_subset_of_4_6_8():
    with pytest.raises(PlanError, match="mod_channels"):
        type("Bad", (Genre,), {
            **_base_kwargs(),
            "id": "bad-mc", "parts": (Part("drums", Groove({})),),
            "mod_channels": {4: 1, 5: 1},
        })


def test_min_channels_must_be_zero_a_key_or_above_max():
    with pytest.raises(PlanError, match="min_channels"):
        type("Bad", (Genre,), {
            **_base_kwargs(),
            "id": "bad-minch",
            "parts": (Part("drums", Groove({}), min_channels=5),),
            "mod_channels": {4: 1, 6: 1, 8: 1},
        })


def test_min_channels_above_max_is_allowed():
    cls = type("Ok", (Genre,), {
        **_base_kwargs(),
        "id": "ok-minch",
        "parts": (Part("drums", Groove({}), min_channels=12),),
        "mod_channels": {4: 1, 8: 1},
    })
    assert cls.id == "ok-minch"


def test_kit_group_rejects_unknown_instrument():
    with pytest.raises(PlanError, match="unknown"):
        type("Bad", (Genre,), {
            **_base_kwargs(),
            "id": "bad-kit",
            "parts": (Part("drums", Groove({}), kit=Kit(groups=(("ks", ("kick", "tom")),))),),
        })


def test_kit_group_rejects_instrument_in_two_groups():
    with pytest.raises(PlanError, match="two kit groups"):
        type("Bad", (Genre,), {
            **_base_kwargs(),
            "id": "bad-kit2",
            "parts": (Part("drums", Groove({}),
                            kit=Kit(groups=(("a", ("kick",)), ("b", ("kick", "snare"))))),),
        })


def test_kit_priority_rejects_instrument_not_in_any_group():
    with pytest.raises(PlanError, match="priority"):
        type("Bad", (Genre,), {
            **_base_kwargs(),
            "id": "bad-kit3",
            "parts": (Part("drums", Groove({}), kit=Kit(groups=(("ks", ("kick",)),),
                                                         priority={"snare": 2})),),
        })


def test_sidechain_trigger_must_be_a_declared_instrument():
    with pytest.raises(PlanError, match="Sidechain trigger"):
        type("Bad", (Genre,), {
            **_base_kwargs(),
            "id": "bad-sc1",
            "parts": (Part("drums", Groove({})),),
            "mix": (Sidechain(triggers=("nope",), targets=("drums",)),),
        })


def test_sidechain_target_must_be_a_declared_part():
    with pytest.raises(PlanError, match="Sidechain target"):
        type("Bad", (Genre,), {
            **_base_kwargs(),
            "id": "bad-sc2",
            "parts": (Part("drums", Groove({})),),
            "mix": (Sidechain(triggers=("kick",), targets=("nope",)),),
        })


def test_duplicate_part_names_rejected():
    with pytest.raises(PlanError, match="duplicate part"):
        type("Bad", (Genre,), {
            **_base_kwargs(),
            "id": "bad-dup",
            "parts": (Part("drums", Groove({})), Part("drums", Groove({}))),
        })


def test_follow_to_unknown_part_rejected():
    with pytest.raises(PlanError, match="unknown part"):
        type("Bad", (Genre,), {
            **_base_kwargs(),
            "id": "bad-follow",
            "parts": (Part("drums", Groove({})), Part("echo", Echo(), follow="lead")),
        })


def test_depends_cycle_rejected():
    with pytest.raises(PlanError, match="cyclic"):
        type("Bad", (Genre,), {
            **_base_kwargs(),
            "id": "bad-cycle",
            "parts": (Part("a", Groove({}), depends=("b",)), Part("b", Groove({}), depends=("a",))),
        })


def test_instrument_without_gmvoice_rejected():
    with pytest.raises(PlanError, match="GmVoice"):
        type("Bad", (Genre,), {
            **_base_kwargs(instruments={"kick": "not-an-instrument"}),
            "id": "bad-gm",
            "parts": (Part("drums", Groove({})),),
        })


def test_section_rejects_both_measures_and_measure_steps():
    with pytest.raises(PlanError, match="measure_steps"):
        Section(measures=5, measure_steps=(14, 14, 10))


def test_section_measure_steps_alone_is_fine():
    sec = Section(measure_steps=(14, 14, 10))
    assert sec.measures == 4   # 既定値のまま（measure_steps の要素数が実際の小節数になる）


def test_valid_declaration_does_not_raise():
    cls = type("Ok", (Genre,), {
        **_base_kwargs(),
        "id": "ok-genre",
        "parts": (Part("drums", Groove({}), kit=Kit(groups=(("ks", ("kick", "snare")),),
                                                     priority={"snare": 2})),),
        "mix": (Sidechain(triggers=("kick",), targets=("drums",)),),
    })
    assert cls.id == "ok-genre"
