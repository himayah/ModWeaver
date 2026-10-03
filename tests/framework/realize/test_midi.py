"""MidiRealizer（DESIGN.md §7.7）の単体・結合テスト。SMF は ``core.midi.parse_midi`` で独立に読み戻す。"""
from __future__ import annotations

import struct

import pytest

from mod_weaver.core import native
from mod_weaver.core.midi import parse_midi
from mod_weaver.errors import PlanError
from mod_weaver.framework.compose import compose, resolve_plan
from mod_weaver.framework.realize import midi as rm
from mod_weaver.framework.score import Arpeggio, Cut, Delay, Glide, NoteEvent, Retrig, Vibrato
from mod_weaver.framework.target import resolve
from tests.framework.realize.test_all_formats import GENRES
from tests.framework.test_realize_mod import make_genre

TPS = 6 * rm.TICK            # 1 step = 6 tracker tick（16分格子）


def _midi(genre, seed=1):
    plan = resolve_plan(genre, seed=seed)
    score = compose(genre, plan, seed=seed, features=frozenset())
    return rm.realize_midi(genre, score, plan, resolve("midi", None, genre, seed)), score


def _title(track):
    return next(bytes(m[3:]).decode() for _t, m in track if m[:2] == b"\xFF\x03")


def _notes(track):
    """(start, end, ch, note, vel) の列。"""
    on, out = {}, []
    for tick, msg in track:
        k, ch = msg[0] & 0xF0, msg[0] & 0x0F
        if k == 0x90 and msg[2]:
            on[(ch, msg[1])] = (tick, msg[2])
        elif k == 0x80 or (k == 0x90 and not msg[2]):
            s, v = on.pop((ch, msg[1]))
            out.append((s, tick, ch, msg[1], v))
    return sorted(out)


# ---- 3 ジャンルの結合 ----

@pytest.mark.parametrize("name", GENRES)
def test_verifies_and_is_deterministic(name):
    data, _ = _midi(GENRES[name])
    assert [i for i in native.verify("midi", data) if i.level == "ERROR"] == []
    assert data == _midi(GENRES[name])[0]


@pytest.mark.parametrize("name", GENRES)
def test_length_matches_the_score(name):
    data, score = _midi(GENRES[name])
    pm = parse_midi(data)
    assert pm.ppq == 480 and pm.format == 1
    expected = sum(score.sections[n].plan.steps * score.sections[n].plan.meter.ticks_per_step
                   for n in score.order) * rm.TICK
    assert max(t for t, _m in pm.tracks[0]) == expected


@pytest.mark.parametrize("name", GENRES)
def test_all_parts_are_present_regardless_of_channel_budget(name):
    """DESIGN.md §7.7: min_channels・channel_cap に関係なく全パートを入れる（tracker では 4ch で外れるパートも入る）。"""
    data, score = _midi(GENRES[name])
    used = {p for s in score.sections.values() for p, ev in s.parts.items()
            if any(isinstance(e, NoteEvent) for e in ev)}
    assert used <= {_title(tr) for tr in parse_midi(data).tracks[1:]}


def test_drums_on_channel_10_and_each_melodic_part_on_its_own_channel():
    data, _ = _midi(GENRES["pop"])
    channels = {_title(tr): {n[2] for n in _notes(tr)} for tr in parse_midi(data).tracks[1:]}
    assert channels["drums"] == {9}
    melodic = {k: c for k, c in channels.items() if k != "drums"}
    assert all(9 not in c and len(c) == 1 for c in melodic.values())
    assert len({next(iter(c)) for c in melodic.values()}) == len(melodic)


def test_first_kick_is_at_its_score_time_with_the_gm_drum_note():
    genre = GENRES["pop"]
    data, score = _midi(genre)
    base, first_kick = 0, None
    for name in score.order:
        sec = score.sections[name]
        kicks = [e.step for e in sec.parts.get("drums", ()) if isinstance(e, NoteEvent) and e.inst == "kick"]
        if kicks:
            first_kick = base + min(kicks) * sec.plan.meter.ticks_per_step * rm.TICK
            break
        base += sec.plan.steps * sec.plan.meter.ticks_per_step * rm.TICK
    drums = next(tr for tr in parse_midi(data).tracks[1:] if _title(tr) == "drums")
    kick = [n for n in _notes(drums) if n[3] == genre.instruments["kick"].gm.drum_note]
    assert kick[0][0] == first_kick


def test_velocity_is_lifted_so_the_loudest_note_is_127():
    data, _ = _midi(GENRES["racing-breaks"])
    assert max(n[4] for tr in parse_midi(data).tracks[1:] for n in _notes(tr)) == 127


# ---- 時間・奏法の単体 ----

def _setup():
    genre = make_genre()
    return genre, rm._Info(genre)


def _tm(base=0):
    return lambda step: base + step * TPS


def test_swing_delays_odd_steps_by_long_minus_step():
    import types

    from mod_weaver.framework.plan import Meter, Swing

    sp = types.SimpleNamespace(meter=Meter(16, 4), swing=Swing(8, 4))     # 2 step ＝ 12 tick。long 8 : short 4
    tm = rm._step_time(1000, sp)
    assert [tm(s) - 1000 for s in range(4)] == [0, 8 * 20, 12 * 20, 12 * 20 + 8 * 20]


def test_chord_expansion_and_strum():
    genre, info = _setup()
    notes = rm._expand_event(info, "comp", NoteEvent(0, "piano", pitch=24, vel=40, dur=4, chord=(0, 4, 7),
                                                      strum_ms=30.0), _tm(), 960, 125)
    assert [round(n.midi - notes[0].midi) for n in notes] == [0, 4, 7]
    ms_per_tick = 60000 / (125 * 480)
    assert [n.start for n in notes] == [0, round(30 / ms_per_tick), round(60 / ms_per_tick)]


def _resolved(info, events, bpm=125, end_tick=4 * 960, noteoffs=()):
    notes = []
    for e in events:
        notes += rm._expand_event(info, "x", e, _tm(), 16 * TPS, bpm)
    rm._resolve_ends(info, notes, list(noteoffs), bpm, end_tick)
    return sorted(notes, key=lambda n: n.start)


def test_end_rules_dur_next_onset_loop_and_noteoff():
    _g, info = _setup()
    a = _resolved(info, [NoteEvent(0, "lead", pitch=30, vel=40, dur=3),     # dur
                         NoteEvent(4, "lead", pitch=30, vel=40),             # ループ: 次の発音で切れる
                         NoteEvent(8, "lead", pitch=30, vel=40)])            # 最後: 区間の終わり
    assert [n.end for n in a] == [3 * TPS, 8 * TPS, 16 * TPS]
    b = _resolved(info, [NoteEvent(0, "lead", pitch=30, vel=40)], noteoffs=[(5 * TPS, "x", "lead")])
    assert b[0].end == 5 * TPS


def test_oneshot_ends_at_its_natural_length_not_the_section():
    _g, info = _setup()
    n = _resolved(info, [NoteEvent(0, "kick", vel=60)])[0]
    expect = info.natural_ticks("kick", None, 125)
    assert n.end == expect and 0 < expect < 16 * TPS


def test_cut_delay_arpeggio_and_retrig():
    _g, info = _setup()
    assert _resolved(info, [NoteEvent(0, "lead", pitch=30, vel=40, arts=(Cut(2),))])[0].end == 2 * rm.TICK
    dl = _resolved(info, [NoteEvent(0, "lead", pitch=30, vel=40, dur=4, arts=(Delay(3),))])[0]
    assert dl.start == 3 * rm.TICK and dl.end == 4 * TPS
    n = _resolved(info, [NoteEvent(0, "lead", pitch=30, vel=40, dur=4, arts=(Arpeggio(3, 7, steps=1),))])[0]
    segs = rm._segments(n)
    assert [round(s.midi - n.midi) for s in segs[:6]] == [0, 3, 7, 0, 3, 7]      # 1 tracker tick ごと
    assert segs[-1].midi == n.midi and segs[-1].end == n.end                      # 奏法の後は基の音が続く
    r = _resolved(info, [NoteEvent(0, "snare", vel=40, dur=2, arts=(Retrig(3),))])[0]
    assert [s.start for s in rm._segments(r)] == list(range(0, 2 * TPS, 3 * rm.TICK))


def test_vibrato_becomes_cc1_and_glide_bends_from_the_previous_note():
    genre, info = _setup()
    notes = _resolved(info, [NoteEvent(0, "lead", pitch=30, vel=40, dur=6, arts=(Vibrato(0x34, at=1, steps=2),)),
                             NoteEvent(4, "lead", pitch=33, vel=40, dur=6, arts=(Glide(steps=2),))])
    voices = rm._build_voices(genre, notes)["x"]
    assert voices[0].cc1 == [(TPS, 4 * 8), (3 * TPS, 0)]
    assert voices[1].glide_from == pytest.approx(-3.0) and voices[1].glide_ticks == 2 * TPS


def test_glide_after_a_finished_note_is_a_plain_note():
    genre, info = _setup()
    notes = _resolved(info, [NoteEvent(0, "lead", pitch=30, vel=40, dur=2),
                             NoteEvent(8, "lead", pitch=33, vel=40, dur=2, arts=(Glide(),))])
    assert rm._build_voices(genre, notes)["x"][1].glide_from is None


def test_microtonal_overlapping_notes_get_separate_channels():
    genre, _ = _setup()
    voices = {"comp": [rm._Voice("comp", "piano", 0, 100, 60.0, 40), rm._Voice("comp", "piano", 0, 100, 63.5, 40)]}
    chan, _ranges = rm._assign_channels(genre, voices)
    assert len({c for (p, _g), c in chan.items() if p == "comp"}) == 2


def test_too_many_distinct_programs_is_a_plan_error_but_equal_programs_share():
    from mod_weaver.core.model import GmVoice
    from mod_weaver.framework.genre import Instrument

    genre, _ = _setup()
    base = genre.instruments["piano"]
    genre.instruments = {f"i{k}": Instrument(patch=base.patch, gm=GmVoice(program=k)) for k in range(16)}
    genre.parts = tuple(type("P", (), {"name": f"p{k}"})() for k in range(16))
    parts = {f"p{k}": [rm._Voice(f"p{k}", f"i{k}", 0, 10, 60.0 + k, 40)] for k in range(16)}
    with pytest.raises(PlanError):
        rm._assign_channels(genre, parts)
    same = {f"p{k}": [rm._Voice(f"p{k}", "i0", 0, 10, 60.0 + k, 40)] for k in range(16)}
    chan, _ = rm._assign_channels(genre, same)               # 同じ program は相乗りして収まる
    assert len(set(chan.values())) < 16


# ---- 検査器 ----

def _smf(events):
    cond = rm._track([(0, rm.CTRL, rm._meta(0x51, (500000).to_bytes(3, "big")))], 10)
    return b"MThd" + struct.pack(">IHHH", 6, 1, 2, 480) + cond + rm._track(events, 10)


def test_verifier_reports_polyphony_over_24_missing_program_and_dangling_notes():
    ons = [(0, rm.ON, bytes([0x90, 40 + i, 64])) for i in range(25)]
    offs = [(5, rm.OFF, bytes([0x80, 40 + i, 0])) for i in range(25)]
    program = [(0, rm.CTRL, bytes([0xC0, 0]))]
    assert {i.code: i.level for i in native.verify("midi", _smf(program + ons + offs))} == {"V09": "WARN"}
    assert "V07" in {i.code for i in native.verify("midi", _smf(ons + offs))}
    assert "V04" in {i.code for i in native.verify("midi", _smf(program + ons))}


def test_generate_reference_files_for_listening():
    """聴き比べ用に ``output/f5-trial/<ジャンル>.mid`` を書き出す（GM 音源・DAW での確認はユーザーが行う）。"""
    import pathlib

    from mod_weaver.core import writer

    out = pathlib.Path("output") / "f5-trial"
    out.mkdir(parents=True, exist_ok=True)
    for name, genre in GENRES.items():
        data, _ = _midi(genre, seed=42)
        writer.write_file(out / f"{name}.mid", data)
        assert (out / f"{name}.mid").stat().st_size > 0
