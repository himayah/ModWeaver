"""Suspense 共通の音色・語彙・和声（DESIGN.md §6.2）。"""
from __future__ import annotations

import cmath
import math

import pytest

from mod_weaver.core import dsp, pitch
from mod_weaver.core.harmony import Registers
from mod_weaver.core.model import Cell, Instrument, MeasureBuffer
from mod_weaver.core.verify import ParsedSample, _Report, _check_loop_boundary
from mod_weaver.profiles import suspense_common as sc

SAMPLES = sc.build_suspense_samples()


def test_sample_table_matches_design():
    assert list(SAMPLES) == list(sc.SAMPLE_KEYS)
    expected = {  # key: (volume, shift, rate_note, pitched, loop)
        "heart": (62, 0, 24, False, None), "anvil": (64, 0, 35, False, None), "swoosh": (44, 0, 24, False, None),
        "drone": (60, -24, 24, True, (30, 380)), "pizz": (56, 0, 24, True, None),
        "strings": (40, 0, 24, True, (100, 2072)), "lead": (46, 12, 24, True, (40, 95)),
    }
    for key, (vol, shift, rate, pitched, loop) in expected.items():
        s = SAMPLES[key]
        assert (s.volume, s.shift, s.rate_note, s.pitched, s.loop) == (vol, shift, rate, pitched, loop), key
        s.validate()
    assert [s.name for s in SAMPLES.values()] == [
        "SubHeartbeat", "MetalAnvil", "NoiseSwoosh", "LowDroneBass", "PizzStab", "TensionStrings", "ScreamingLead"]
    assert sc.SAMPLE_KEYS.index("heart") + 1 == sc.HEART and sc.SAMPLE_KEYS.index("lead") + 1 == sc.LEAD


def test_sample_lengths_and_durations():
    def sec(key):
        s = SAMPLES[key]
        return len(s.data) / dsp.sample_rate(s.rate_note)
    assert sec("heart") == pytest.approx(0.40, abs=0.001)
    assert sec("anvil") == pytest.approx(0.90, abs=0.001)
    assert sec("swoosh") == pytest.approx(0.90, abs=0.001)
    assert sec("pizz") == pytest.approx(0.40, abs=0.001)
    assert len(SAMPLES["drone"].data) == 60 + 760 and len(SAMPLES["strings"].data) == 200 + 4144
    assert len(SAMPLES["lead"].data) == 80 + 190
    assert sum(len(s.data) for s in SAMPLES.values()) < 60_000


def test_all_samples_have_headroom_and_signal():
    for key, s in SAMPLES.items():
        vals = [b - 256 if b > 127 else b for b in s.data]
        assert 60 <= max(abs(v) for v in vals) <= 127, key


def test_loops_are_click_free_by_verify_rule():
    for key in ("drone", "strings", "lead"):
        s = SAMPLES[key]
        ps = ParsedSample(b"", s.length_words, 0, s.volume, s.loop[0], s.loop[1], s.data)
        rep = _Report()
        _check_loop_boundary(1, ps, rep)
        assert not rep._items, key


def _bin_energy(data: bytes, start: int, length: int, k: int) -> float:
    x = [(b - 256 if b > 127 else b) for b in data[start:start + length]]
    return abs(sum(v * cmath.exp(-2j * math.pi * k * i / length) for i, v in enumerate(x)))


def test_loop_content_frequencies_follow_design():
    """ループ本体の主成分が設計の周期数 K に立っている（DESIGN.md §6.2 の K, L と §3.1 の spc）。"""
    drone = SAMPLES["drone"]
    e = {k: _bin_energy(drone.data, 60, 760, k) for k in range(1, 12)}
    assert max(e, key=e.get) == 6                         # K=6
    lead = SAMPLES["lead"]
    e = {k: _bin_energy(lead.data, 80, 190, k) for k in range(1, 20)}
    assert max(e, key=e.get) == 12                        # K=12
    # 実効周波数は目標との誤差が 1 cent 未満
    for key, K, L in (("drone", 6, 760), ("lead", 12, 190)):
        s = SAMPLES[key]
        cents = 1200 * math.log2(K * dsp.content_spc(s.rate_note, s.shift) / L)
        assert abs(cents) < 1.0
    # strings: 131−130 = 1 cycle → 基準音（C-3）で SR/L ≈ 2.0Hz のうなり
    assert dsp.sample_rate(24) / 4144 == pytest.approx(2.0, abs=0.001)
    strings = SAMPLES["strings"]
    e = {k: _bin_energy(strings.data, 200, 4144, k) for k in (129, 130, 131, 132, 137, 138, 139, 140)}
    assert min(e[130], e[131], e[138], e[139]) > 4 * max(e[129], e[132], e[137], e[140])


def test_drone_low_note_pitch():
    """drone は shift −24: logical 0（C-1, 65.41Hz）を t=24（C-3）で発音する。"""
    inst = Instrument(4, SAMPLES["drone"])
    assert inst.cell(0).note == 24
    f = dsp.sample_rate(24) * 6 / 760            # C-3 で再生したときの基音
    assert f == pytest.approx(pitch.hz(0), rel=0.001)


def test_swoosh_start_row_and_row_seconds():
    assert sc.row_seconds(60) == pytest.approx(0.25)
    for bpm in (64, 66, 68, 70, 72):
        assert sc.swoosh_start_row(16, bpm) == 12
    for bpm in (138, 140, 142, 144, 146, 148):
        assert sc.swoosh_start_row(16, bpm) in (7, 8)
    assert sc.swoosh_start_row(16, 64) == 16 - round(0.9 / (15 / 64))


def test_oneshot_off_row_and_put():
    pizz = Instrument(5, SAMPLES["pizz"])
    assert sc.oneshot_off_row(pizz, 10, 68) == 10 + math.ceil(0.4 / (15 / 68))
    buf = MeasureBuffer(16, sc.CHANNEL_PLAN, strict=True)
    sc.put_oneshot_off(buf, sc.CH_LEAD, 2, pizz, 68)
    assert buf.get(2 + math.ceil(0.4 / (15 / 68)), sc.CH_LEAD) == Cell(None, 0, vol=0)
    sc.put_oneshot_off(buf, sc.CH_LEAD, 15, pizz, 68)     # measure 外なら何もしない
    assert buf.get(15, sc.CH_LEAD).is_empty


def test_channel_plan_priorities_and_allowed():
    p = sc.CHANNEL_PLAN
    assert [sorted(r.allowed) for r in p] == [[1, 2, 3], [4], [5, 6], [5, 7]]
    assert p[0].priority[sc.ANVIL] > p[0].priority[sc.SWOOSH] > p[0].priority[sc.HEART]
    assert p[2].priority[sc.PIZZ] > p[2].priority[sc.STRINGS] and p[3].priority[sc.PIZZ] > p[3].priority[sc.LEAD]


def test_registers_and_arp_range():
    assert sc.BASS_REG == (0, 11) and sc.HARMONY_REG == (17, 28) and sc.PIZZ_REG == (24, 35) and sc.LEAD_REG == (24, 41)
    assert isinstance(sc.REGISTERS, Registers)
    # HARMONY_REG の最高音でも最大アルペジオ +7 が t ≤ 35 に収まる
    assert sc.HARMONY_REG[1] + 7 <= 35


@pytest.mark.parametrize("name", sorted(sc.PROGRESSIONS))
def test_progressions_voiced(name):
    slots = sc.voice_progression(name)
    assert len(slots) == 4 and all(s.measures == 1 for s in slots)
    for s in slots:
        c = s.chord
        assert sc.BASS_REG[0] <= c.bass <= sc.BASS_REG[1]
        assert sc.HARMONY_REG[0] <= c.harmony <= sc.HARMONY_REG[1]
        assert c.arp in (0x36, 0x37, 0x47) and not c.explicit
        assert c.harmony + max(c.arp >> 4, c.arp & 0xF) <= 35


def test_pedal_progression_pins_bass_to_c():
    labels = [s.chord.label for s in sc.voice_progression("pedal")]
    assert labels == ["Cdim", "Db/C", "Cdim", "B/C"]
    assert all(s.chord.bass == 0 for s in sc.voice_progression("pedal"))


def test_other_progressions_labels():
    assert [s.chord.label for s in sc.voice_progression("tritone")] == ["Cm", "F#dim", "Fm", "Bdim"]
    assert [s.chord.label for s in sc.voice_progression("phrygian")] == ["Cm", "Dbmaj7", "Bbm", "C"]


def test_dim_chords_use_diminished_scale():
    dim = sc.voice_progression("pedal")[0].chord
    assert {n % 12 for n in dim.scale_tones} >= {0, 2, 3, 5, 6, 8, 9, 11}


def test_pizz_root_note_in_pizz_reg():
    for slot in sc.voice_progression("tritone"):
        n = sc.SuspenseBase.pizz_root_note(slot.chord)
        assert sc.PIZZ_REG[0] <= n <= sc.PIZZ_REG[1] and n % 12 == slot.chord.harmony % 12


def test_heartbeat_helper_rows():
    heart = Instrument(1, SAMPLES["heart"])
    buf = MeasureBuffer(16, sc.CHANNEL_PLAN, strict=True)
    sc.heartbeat(buf, heart, range(0, 16, 4), 40, 28)
    lubs = [r for r in range(16) if buf.get(r, 0).vol == 40]
    dubs = [r for r in range(16) if buf.get(r, 0).vol == 28]
    assert lubs == [0, 4, 8, 12] and dubs == [2, 6, 10, 14]


def test_progression_summary_text():
    assert "Pedal Tone Terror" in sc.progression_summary("Theme A", "pedal")
    assert "Cdim - Db/C - Cdim - B/C" in sc.progression_summary("Theme A", "pedal")


def test_grammar_missing_kind_raises():
    from tests.helpers import DummyProfile

    class P(sc.SuspenseBase):
        id = "p"; display_name = "P"; description = "d"; title = "P"; default_filename = "p.mod"
        tempo_choices = (60,)
        def plan(self, rng): raise NotImplementedError

    from mod_weaver.core.model import MeasureCtx, PatternCtx
    pctx = PatternCtx("zzz", 0, 60, 0, 0, 0.5, True)
    with pytest.raises(KeyError, match="no grammar"):
        P().compose_measure(MeasureCtx(pctx, 0, 4, None, 0, False, {}), None, None, None)
