"""歌声の合唱（``Choir``。DESIGN.md §13.4.3・P5）: 和音の各声を同じ母音で同時に歌う。"""
import dataclasses

import pytest

from mod_weaver import engine
from mod_weaver.core.model import GmVoice
from mod_weaver.errors import PlanError
from mod_weaver.framework.compose import compose, resolve_plan
from mod_weaver.framework.genre import Part, Voice
from mod_weaver.framework.gens import Choir
from mod_weaver.framework.score import NoteEvent
from mod_weaver.framework.target import resolve
from mod_weaver.genres.enka import EnkaGenre


def _choir_genre(voices=3, poly=3):
    secs = {k: (dataclasses.replace(v, parts=v.parts | {"choir"}) if "vocal" in v.parts else v)
            for k, v in EnkaGenre.sections.items()}

    class TestChoir(EnkaGenre):
        id = "test-choir"
        instruments = {**EnkaGenre.instruments, "choir": Voice(GmVoice(program=52), timbre="choir", volume=40)}
        parts = EnkaGenre.parts + (Part("choir", Choir("choir", voices=voices), poly=poly, min_channels=8,
                                        requires=frozenset({"voice"})),)
        sections = secs
    return TestChoir()


def _events(g, fmt="it", seed=3):
    plan = resolve_plan(g, seed)
    t = resolve(fmt, None, g, seed)
    sc = compose(g, plan, seed, t.features | {"voice"})
    return plan, sc


def test_choir_writes_one_simultaneous_note_per_chord_tone_until_the_next_change():
    g = _choir_genre()
    plan, sc = _events(g)
    sec = sc.sections["chorus"]
    notes = sorted((e for e in sec.parts["choir"] if isinstance(e, NoteEvent)), key=lambda e: (e.step, e.pitch))
    by_step = {}
    for e in notes:
        by_step.setdefault(e.step, []).append(e)
    assert by_step and all(len(v) == 3 for v in by_step.values())
    assert all(e.syl.text == "あ" for e in notes)
    steps = sorted(by_step)
    for a, b in zip(steps, steps[1:]):                                    # 次の和音の変わり目まで伸ばす
        assert {e.dur for e in by_step[a]} == {b - a}
    assert steps[-1] + by_step[steps[-1]][0].dur <= sec.plan.steps            # 区間の終わりを超えない
    for v in by_step.values():                                            # 声部は三和音の間隔（根音からの半音数が昇順に 3 つ）
        ps = [e.pitch - v[0].pitch for e in v]
        assert ps[0] == 0 and ps[1] in (3, 4, 2, 5) and ps[2] in (6, 7, 8)


def test_choir_part_is_absent_without_voice_or_with_too_few_channels():
    g = _choir_genre()
    plan = resolve_plan(g, 3)
    sc = compose(g, plan, 3, resolve("it", None, g, 3).features)           # --voice なし
    assert "choir" in sc.skipped_parts
    b = engine.build(g, 3, "xm", voice="formant", channels=7)             # 予算 7 < min_channels 8: 合唱は外れる
    assert b.channels <= 7


@pytest.mark.parametrize("fmt", ["it", "xm", "s3m", "midi"])
def test_choir_song_builds_and_verifies_in_every_voice_format(fmt):
    g = _choir_genre()
    b = engine.build(g, 3, fmt, voice="formant")
    assert not [i for i in engine.verify_data(b) if i.level == "ERROR"]
    plain = engine.build(_choir_genre(), 3, fmt, voice=None)
    assert b.channels > plain.channels                                    # 声部の lane が足される（上限いっぱいの形式を除く）
    if fmt in ("it", "xm"):
        assert b.channels >= plain.channels + 4                           # 歌 1 + 合唱 3（MIDI は合唱が 1 チャンネルを共有）


def test_more_simultaneous_voices_than_poly_is_still_an_error():
    g = _choir_genre(voices=3, poly=2)
    with pytest.raises(PlanError, match="same priority|exceed"):
        _events(g)
