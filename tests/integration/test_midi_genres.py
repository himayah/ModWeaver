"""全ジャンルの --format midi（DESIGN.md §7.7）。SMF の独立パースには mido（開発専用依存）を使う。"""
from __future__ import annotations

import io

import pytest

from mod_weaver import engine
from mod_weaver.core import native
DRUM_CHANNEL = 9      # GM のドラムは MIDI チャンネル 10（0 始まりで 9）
PPQ = 480

mido = pytest.importorskip("mido")
GENRES = [g.id for g in engine.list_genres()]


def render(genre, seed=123456, **kw):
    built = engine.build(engine.get_genre(genre), seed, "midi", **kw)
    return built, mido.MidiFile(file=io.BytesIO(built.data))


def score_seconds(score) -> float:
    """Score の時間軸の長さ（テンポの変化を含む）。"""
    bpm, total = score.bpm, 0.0
    for name in score.order:
        sec = score.sections[name]
        tempo = {t.step: t.bpm for t in sec.tempo}
        for step in range(sec.plan.steps):
            bpm = tempo.get(step, bpm)
            total += sec.plan.meter.ticks_per_step * 2.5 / bpm
    return total


@pytest.mark.parametrize("genre", GENRES)
def test_midi_is_valid_and_matches_the_score(genre):
    built, mf = render(genre)
    assert not [i for i in native.verify("midi", built.data) if i.level == "ERROR"]
    assert mf.type == 1 and mf.ticks_per_beat == PPQ
    assert abs(mf.length - score_seconds(built.score)) < 0.05
    tempos = [m.tempo for m in mf.tracks[0] if m.type == "set_tempo"]
    assert tempos[0] == 60_000_000 // built.plan.bpm
    note_ons = [m for tr in mf.tracks for m in tr if m.type == "note_on" and m.velocity]
    assert note_ons and all(0 <= m.note <= 127 for m in note_ons)
    g = built.genre
    if any(i.gm.is_drum for i in g.instruments.values()):
        assert any(m.channel == DRUM_CHANNEL for m in note_ons)


def test_tempo_option_reaches_midi_tempo():
    _built, mf = render("nostalgic", tempo=engine.TempoRequest(140, 140))
    assert [m.tempo for m in mf.tracks[0] if m.type == "set_tempo"][0] == 60_000_000 // 140


def test_free_jazz_tempo_curve_becomes_tempo_events():
    _built, mf = render("free-jazz")
    assert len([m for m in mf.tracks[0] if m.type == "set_tempo"]) > 20


@pytest.mark.parametrize("genre, sig", [("nostalgic", (4, 4)), ("march", (2, 4)), ("swing-jazz", (4, 4))])
def test_time_signature(genre, sig):
    _built, mf = render(genre)
    ts = [m for m in mf.tracks[0] if m.type == "time_signature"]
    assert (ts[0].numerator, ts[0].denominator) == sig


def test_prog_rock_meter_changes_are_written():
    _built, mf = render("prog-rock")
    sigs = {(m.numerator, m.denominator) for m in mf.tracks[0] if m.type == "time_signature"}
    assert len(sigs) >= 2


def test_microtonal_degrees_become_pitch_bends():
    """maqam の中立音程（350・1050 セント）は専用チャンネルの固定ベンドになる（±50 セント）。"""
    _built, mf = render("maqam")
    bends = [m.pitch for tr in mf.tracks for m in tr if m.type == "pitchwheel" and m.pitch != 0]
    assert bends and max(abs(b) for b in bends) > 1000


@pytest.mark.parametrize("genre", ["calm", "orchestral"])
def test_channel_volume_is_full_and_loudest_note_is_velocity_127(genre):
    """音量の底上げ（DESIGN.md §7.9）: 全チャンネルの CC7 が 127、最も大きい音が velocity 127。"""
    _built, mf = render(genre)
    channels = {m.channel for tr in mf.tracks for m in tr if m.type == "note_on"}
    cc7 = {m.channel: m.value for tr in mf.tracks for m in tr if m.type == "control_change" and m.control == 7}
    assert channels <= set(cc7) and set(cc7.values()) == {127}
    assert max(m.velocity for tr in mf.tracks for m in tr if m.type == "note_on") == 127
