from __future__ import annotations

import math
import random

import pytest

from mod_weaver.core import dsp, pitch
from mod_weaver.errors import SampleConstraintError
from tests.conftest import load_reference


def test_content_spc_matches_design_table():
    # DESIGN.md §3.1 の例表（rate_note=C-3）
    assert dsp.content_spc(24, -24) == pytest.approx(126.7, abs=0.05)
    assert dsp.content_spc(24, -12) == pytest.approx(63.4, abs=0.05)
    assert dsp.content_spc(24, 0) == pytest.approx(31.68, abs=0.01)
    assert dsp.content_spc(24, 12) == pytest.approx(15.84, abs=0.01)


def test_heard_pitch_follows_n_equals_t_plus_shift():
    """rate_note で作った波形を tracker note t で鳴らすと logical note t+shift（n = t + shift）が聞こえる（DESIGN.md §3.1）。

    Period 表の丸め誤差（最大約 8 cent）の範囲で一致する。spc は発音 note によらず一定。
    """
    for shift in (-24, -12, 0, 12):
        spc = dsp.content_spc(24, shift)
        for t in range(0, 36):
            heard = (dsp.CLOCK / (2 * pitch.PERIODS[t])) / spc
            cents = 1200 * math.log2(heard / pitch.hz(t + shift))
            assert abs(cents) < 10, (shift, t, cents)


def test_loop_design_reproduces_design_table():
    def best(spc, lmax):
        return dsp.loop_design(spc, lmax)[0]

    c, k, l = best(dsp.content_spc(24, 0), 200)
    assert (k, l) == (6, 190) and c == pytest.approx(0.49, abs=0.02)
    cands = dsp.loop_design(dsp.content_spc(24, -24), 800)
    assert any(k == 6 and l == 760 and c == pytest.approx(0.49, abs=0.02) for c, k, l in cands)
    c, k, l = best(dsp.content_spc(24, 12), 200)
    assert (k, l) == (12, 190) and c == pytest.approx(0.49, abs=0.02)
    # 旧 Pad/Flute（K=32, L=1024）は約 −17.6 cent
    old = 1200 * math.log2(32 * dsp.content_spc(24, 0) / 1024)
    assert old == pytest.approx(-17.6, abs=0.1)
    assert all(l % 2 == 0 for _, _, l in cands) and cands == sorted(cands, key=lambda c: (abs(c[0]), c[1]))
    assert dsp.loop_design(31.7, 200, k_step=2)[0][1] % 2 == 0


def test_partials():
    assert dsp.partials_saw(3) == [(1.0, 1.0), (2.0, 0.5), (3.0, pytest.approx(1 / 3))]
    assert [m for m, _ in dsp.partials_square(6)] == [1.0, 3.0, 5.0]
    assert dsp.partials_square(5)[1][1] == pytest.approx(1 / 3)
    tri = dsp.partials_triangle(7)
    assert [m for m, _ in tri] == [1.0, 3.0, 5.0, 7.0]
    assert [w for _, w in tri] == [pytest.approx(1.0), pytest.approx(-1 / 9), pytest.approx(1 / 25), pytest.approx(-1 / 49)]


def test_additive_and_nyquist_exclusion():
    parts = [(1.0, 1.0), (2.0, 0.5)]
    t = 0.001
    full = math.sin(2 * math.pi * 100 * t) + 0.5 * math.sin(2 * math.pi * 200 * t)
    assert dsp.additive(100, t, parts) == pytest.approx(full)
    assert dsp.additive(100, t, parts, nyquist=150) == pytest.approx(math.sin(2 * math.pi * 100 * t))
    assert dsp.additive(100, t, parts, nyquist=100) == 0.0     # f >= nyquist は除外


def test_exp_decay_and_adsr():
    assert dsp.exp_decay(0, 5) == 1.0 and dsp.exp_decay(1, 5) == pytest.approx(math.exp(-5))
    a = lambda t: dsp.adsr(t, 1.0, 0.1, 0.2, 0.5, 0.2)
    assert a(-0.1) == 0.0 and a(0) == 0.0 and a(0.05) == pytest.approx(0.5)
    assert a(0.1) == pytest.approx(1.0) and a(0.2) == pytest.approx(0.75) and a(0.5) == 0.5
    assert a(0.9) == pytest.approx(0.25) and a(1.0) == 0.0 and a(2.0) == 0.0
    assert dsp.adsr(0.5, 1.0, 0, 0, 0.7, 0) == 0.7            # a=d=r=0 でも安全


def test_noise_lp_properties():
    r1, r2 = random.Random(1), random.Random(1)
    out = dsp.noise_lp(r1, 500, 0.65, 0.15)
    assert len(out) == 500 and out == dsp.noise_lp(r2, 500, 0.65, 0.15)
    assert all(abs(v) <= 1.0 for v in out)
    assert dsp.noise_lp(random.Random(1), 1, 0.3, 0.9)[0] == pytest.approx(0.7 * random.Random(1).uniform(-1, 1))

    def roughness(xs):
        return sum(abs(xs[i + 1] - xs[i]) for i in range(len(xs) - 1)) / len(xs)
    dark = dsp.noise_lp(random.Random(2), 4000, 0.9, 0.9)
    bright = dsp.noise_lp(random.Random(2), 4000, 0.1, 0.1)
    assert roughness(dark) < roughness(bright)               # a が大きいほど暗い


def test_one_pole_lp_equals_legacy_snare_filter():
    r_new, r_old = random.Random(42), random.Random(42)
    raw = [r_new.uniform(-1.0, 1.0) for _ in range(300)]
    lp, legacy = 0.0, []
    for _ in range(300):
        lp = lp * 0.35 + r_old.uniform(-1.0, 1.0) * 0.65
        legacy.append(lp)
    assert dsp.one_pole_lp(raw, 0.35) == pytest.approx(legacy, abs=1e-12)


def test_diff_hp_equals_legacy_hihat_filter():
    xs = [0.3, -0.2, 0.5, 0.5, 0.1]
    assert dsp.diff_hp(xs) == pytest.approx([0.3, -0.5, 0.7, 0.0, -0.4])


def test_seamless_loop_periodicity():
    body = dsp.seamless_loop(760, 6, [(1, 1.0), (3, 0.5), (0.5, 0.6)])
    assert len(body) == 760
    cont = lambda i: sum(w * math.sin(2 * math.pi * 6 * m * i / 760) for m, w in [(1, 1.0), (3, 0.5), (0.5, 0.6)])
    assert body[0] == pytest.approx(cont(0)) and cont(760) == pytest.approx(cont(0), abs=1e-9)   # x[L] は x[0] に一致
    # 境界の段差は内部の隣接差と同程度（連続）
    max_step = max(abs(body[i + 1] - body[i]) for i in range(759))
    assert abs(body[0] - body[-1]) <= max_step


def test_seamless_rejects_non_integer_cycles():
    with pytest.raises(SampleConstraintError, match="not an integer"):
        dsp.seamless_loop(760, 5, [(0.5, 1.0)])
    with pytest.raises(SampleConstraintError):
        dsp.seamless_terms(100, [(2.5, 1.0)])
    with pytest.raises(SampleConstraintError):
        dsp.seamless_terms(100, [(50, 1.0)])          # k >= length/2（エイリアス）
    with pytest.raises(SampleConstraintError):
        dsp.seamless_terms(100, [(0, 1.0)])
    assert len(dsp.seamless_terms(4144, [(130, 1.0), (131, 1.0), (138, 0.8), (139, 0.8), (260, .35)])) == 4144


def test_circular_filter_keeps_boundary_continuous():
    body = dsp.seamless_loop(190, 6, [(1, 1.0), (2, 0.5)])
    out = dsp.circular(lambda d: dsp.one_pole_lp(d, 0.35), body)
    assert len(out) == 190
    max_step = max(abs(out[i + 1] - out[i]) for i in range(189))
    assert abs(out[0] - out[-1]) <= max_step
    naive = dsp.one_pole_lp(body, 0.35)                       # 単純な因果 LP は境界が不連続になりうる
    assert abs(naive[0] - naive[-1]) >= abs(out[0] - out[-1])


def test_with_attack():
    body = dsp.seamless_loop(190, 6, [(1, 1.0)])
    out = dsp.with_attack(body, 60)
    assert len(out) == 190 + 60
    assert out[:60] != body[:60] and out[60:] == body
    assert out[0] == 0.0                                        # 窓の先頭は 0
    window = [out[i] / body[190 - 60 + i] for i in range(1, 60) if abs(body[190 - 60 + i]) > 1e-6]
    assert all(0 < w < 1.0001 for w in window)
    max_step = max(abs(body[i + 1] - body[i]) for i in range(189))
    assert abs(out[59] - out[60]) <= max_step                   # アタック末尾 → ループ先頭の段差
    win = [0.5 * (1 - math.cos(math.pi * i / 60)) for i in range(60)]
    assert all(b >= a for a, b in zip(win, win[1:]))            # 窓は単調増加
    for bad in (0, 3, 191, -2):
        with pytest.raises(SampleConstraintError):
            dsp.with_attack(body, bad)


def test_full_loop_recipe_passes_verify_v11():
    """drone のレシピ（DESIGN.md §4.4）で作ったループが V11（境界段差）を満たす。"""
    from mod_weaver.core.model import SampleSpec
    from mod_weaver.core.verify import ParsedSample, _Report, _check_loop_boundary

    body = dsp.seamless_terms(760, [(6 * h, 1.0 / h) for h in (1, 3, 5, 7)] + [(3, 0.6)])
    body = dsp.circular(lambda d: dsp.one_pole_lp(d, 0.35), body)
    body = [math.tanh(1.1 * x) for x in body]
    data = dsp.to_pcm(dsp.with_attack(body, 60))
    spec = SampleSpec("drone", data, 60, loop=(30, 380))
    spec.validate()
    ps = ParsedSample(b"", spec.length_words, 0, 60, 30, 380, data)
    rep = _Report()
    _check_loop_boundary(1, ps, rep)
    assert not rep._items
