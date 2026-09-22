"""core/synth.py: 直交レイヤー方式（Patch → SampleSpec）。"""
from __future__ import annotations

import math

import pytest

from mod_weaver.core import dsp, synth
from mod_weaver.core.pitch import hz
from mod_weaver.errors import SampleConstraintError


def _signed_samples(data: bytes) -> list[int]:
    return [b - 256 if b > 127 else b for b in data]


# ------------------------------------------------------------ Patch のバリデーション
def test_patch_requires_at_least_one_layer():
    with pytest.raises(SampleConstraintError, match="at least one layer"):
        synth.Patch("x", (), synth.OneShot(0.1), pitched=False)


def test_loop_finish_rejects_non_tone_layer():
    layer = synth.WeightedLayer(synth.NoiseLayer())
    with pytest.raises(SampleConstraintError, match="only supports ToneLayer"):
        synth.Patch("x", (layer,), synth.Loop(190, 60), pitched=True)


def test_loop_finish_rejects_oneshot_only_fields():
    layer = synth.WeightedLayer(synth.ToneLayer(((6.0, 1.0, None),)))
    for bad_kwargs in (
        {"post_filter": synth.FilterSpec("lp", a=0.3)},
        {"decay_alpha": 5.0},
        {"attack_ms": 10.0},
        {"tail_fade_ms": 5.0},
    ):
        with pytest.raises(SampleConstraintError, match="OneShot-only"):
            synth.Patch("x", (layer,), synth.Loop(190, 60), pitched=True, **bad_kwargs)


def test_loop_finish_rejects_decaying_partials():
    layer = synth.WeightedLayer(synth.ToneLayer(((6.0, 1.0, 5.0),)))
    with pytest.raises(SampleConstraintError, match="cannot decay"):
        synth.Patch("x", (layer,), synth.Loop(190, 60), pitched=True)


def test_filter_spec_rejects_unknown_kind():
    with pytest.raises(SampleConstraintError, match="unknown filter kind"):
        synth.FilterSpec("bandpass")


def test_noise_layer_rejects_decay_and_rise_together():
    with pytest.raises(SampleConstraintError, match="mutually exclusive"):
        synth.NoiseLayer(decay_alpha=10.0, rise_power=2.0)


def test_lp_sweep_filter_invalid_on_tone_layer():
    patch = synth.Patch(
        "x", (synth.WeightedLayer(synth.ToneLayer(((1.0, 1.0, 5.0),), filter=synth.FilterSpec("lp_sweep"))),),
        synth.OneShot(0.05), pitched=True,
    )
    with pytest.raises(SampleConstraintError, match="only valid as noise generation"):
        synth.render(patch)


# ------------------------------------------------------------ OneShot / ToneLayer
def test_oneshot_tone_layer_matches_manual_additive_pitched():
    """pitched=True: f0 = hz(rate_note+shift) に対する mult の比率として解釈される。"""
    patch = synth.Patch(
        "Tone", (synth.WeightedLayer(synth.ToneLayer(((1.0, 1.0, None),))),),
        synth.OneShot(0.01), pitched=True, rate_note=24, shift=0, saturate=None, peak=1.0,
    )
    spec = synth.render(patch)
    rate = dsp.sample_rate(24)
    f0 = hz(24)
    n = round(0.01 * rate)
    expected = [math.sin(2 * math.pi * f0 * (i / rate)) for i in range(n)]
    m = max(abs(x) for x in expected)
    expected = [x / m for x in expected]
    got = _signed_samples(spec.data)
    assert len(got) in (len(expected), len(expected) + 1)      # pad_even で奇数長なら +1
    for g, e in zip(got, expected):
        assert g == pytest.approx(round(e * 127), abs=1)


def test_oneshot_tone_layer_unpitched_mult_is_absolute_hz():
    """pitched=False: mult は絶対 Hz（f0=1.0）。"""
    patch = synth.Patch(
        "Click", (synth.WeightedLayer(synth.ToneLayer(((440.0, 1.0, None),))),),
        synth.OneShot(0.01), pitched=False, rate_note=24, peak=1.0,
    )
    spec = synth.render(patch)
    rate = dsp.sample_rate(24)
    n = round(0.01 * rate)
    expected = [math.sin(2 * math.pi * 440.0 * (i / rate)) for i in range(n)]
    got = _signed_samples(spec.data)
    for g, e in zip(got, expected):
        assert g == pytest.approx(round(e * 127), abs=1)
    assert spec.pitched is False


def test_per_partial_decay_alpha_differs():
    """倍音ごとに異なる decay_alpha が個別に効くこと（早く減衰する方が後半で振幅が小さい）。"""
    patch = synth.Patch(
        "Pluck",
        (synth.WeightedLayer(synth.ToneLayer(((1.0, 1.0, 3.0), (2.0, 1.0, 30.0)))),),
        synth.OneShot(0.3), pitched=True, saturate=None, peak=1.0,
    )
    spec = synth.render(patch)
    xs = _signed_samples(spec.data)
    early_energy = sum(abs(v) for v in xs[: len(xs) // 8])
    late_energy = sum(abs(v) for v in xs[-len(xs) // 8:])
    assert late_energy < early_energy


# ------------------------------------------------------------ OneShot / PitchSweepLayer
def test_pitch_sweep_layer_is_unpitched_one_shot():
    patch = synth.Patch(
        "Kick",
        (synth.WeightedLayer(synth.PitchSweepLayer(120.0, 85.0, 25.0, 14.0)),),
        synth.OneShot(0.25), pitched=False, saturate=1.3, volume=60,
    )
    spec = synth.render(patch)
    spec.validate()
    assert spec.pitched is False and spec.loop is None
    assert len(spec.data) % 2 == 0 and len(spec.data) > 0


# ------------------------------------------------------------ OneShot / NoiseLayer
def test_noise_layer_decay_shape_fades_out():
    patch = synth.Patch(
        "Hat", (synth.WeightedLayer(synth.NoiseLayer(decay_alpha=40.0)),),
        synth.OneShot(0.2), pitched=False, saturate=1.1,
    )
    spec = synth.render(patch)
    xs = _signed_samples(spec.data)
    assert max(abs(v) for v in xs[-10:]) < max(abs(v) for v in xs[:10])


def test_noise_layer_rise_shape_swells_in():
    patch = synth.Patch(
        "Swoosh", (synth.WeightedLayer(synth.NoiseLayer(rise_power=2.2)),),
        synth.OneShot(0.3), pitched=False, saturate=None, peak=1.0,
    )
    spec = synth.render(patch)
    xs = _signed_samples(spec.data)
    assert abs(xs[0]) <= 2                                   # ほぼ 0 から始まる
    assert max(abs(v) for v in xs[-20:]) > max(abs(v) for v in xs[:20])


def test_lp_sweep_noise_uses_noise_lp():
    patch = synth.Patch(
        "Swoosh", (synth.WeightedLayer(synth.NoiseLayer(filter=synth.FilterSpec("lp_sweep", a_start=0.65, a_end=0.15))),),
        synth.OneShot(0.05), pitched=False, saturate=None,
    )
    spec = synth.render(patch)
    spec.validate()


# ------------------------------------------------------------ 合成（複数レイヤーの重み付き和）
def test_multiple_layers_are_weighted_and_summed():
    tone = synth.WeightedLayer(synth.ToneLayer(((1.0, 1.0, None),)), weight=0.6)
    noise = synth.WeightedLayer(synth.NoiseLayer(decay_alpha=30.0), weight=0.4)
    patch = synth.Patch("Mix", (tone, noise), synth.OneShot(0.05), pitched=True, saturate=None)
    spec = synth.render(patch)
    spec.validate()
    assert len(spec.data) > 0


# ------------------------------------------------------------ peak=None（正規化スキップ）
def test_peak_none_skips_normalization():
    """peak=None: 生の混合信号をそのまま tanh に渡す（正規化で振幅を底上げしない）。"""
    layer = synth.ToneLayer(((1.0, 0.3, None),))                # 振幅 0.3 の弱い信号
    normalized = synth.render(synth.Patch(
        "N", (synth.WeightedLayer(layer),), synth.OneShot(0.01), pitched=True, saturate=None, peak=0.95,
    ))
    raw = synth.render(synth.Patch(
        "R", (synth.WeightedLayer(layer),), synth.OneShot(0.01), pitched=True, saturate=None, peak=None,
    ))
    n_peak = max(abs(v) for v in _signed_samples(normalized.data))
    r_peak = max(abs(v) for v in _signed_samples(raw.data))
    assert n_peak > r_peak                                        # 正規化ありの方がピークが大きい
    assert r_peak == pytest.approx(round(0.3 * 127), abs=1)        # 正規化なしは振幅がそのまま反映される


def test_peak_none_also_works_for_loop():
    layer = synth.ToneLayer(((6.0, 0.4, None),))
    patch = synth.Patch(
        "L", (synth.WeightedLayer(layer),), synth.Loop(190, 0), pitched=True, saturate=None, peak=None,
    )
    spec = synth.render(patch)
    spec.validate()


# ------------------------------------------------------------ Loop（attack_samples=0、アタックなし）
def test_loop_with_zero_attack_starts_at_sample_zero():
    layer = synth.ToneLayer(((32.0, 0.55, None), (64.0, 0.22, None)))
    patch = synth.Patch(
        "Pad", (synth.WeightedLayer(layer),), synth.Loop(1024, 0), pitched=True, saturate=None, peak=None,
    )
    spec = synth.render(patch)
    spec.validate()
    assert spec.loop == (0, 512) and spec.length_words == 512
    body_only = dsp.seamless_terms(1024, [(32.0, 0.55), (64.0, 0.22)])
    got = _signed_samples(spec.data)
    for g, e in zip(got, body_only):
        assert g == pytest.approx(round(e * 127), abs=1)


# ------------------------------------------------------------ post_filter（混合後、型の異なるレイヤーの合算に）
def test_post_filter_applies_to_mixed_layers_before_decay():
    """hihat 型: ノイズ＋決定的なトーンの和を一括で HP に通してから減衰させる。"""
    noise = synth.NoiseLayer()                                    # decay_alpha=rise_power=None（層内は無包絡）
    tone = synth.ToneLayer(((3200.0, 0.25, None), (4400.0, 0.25, None)))
    patch = synth.Patch(
        "Hat", (synth.WeightedLayer(noise, weight=0.85), synth.WeightedLayer(tone, weight=0.85)),
        synth.OneShot(0.045), pitched=False, post_filter=synth.FilterSpec("hp"),
        decay_alpha=65.0, saturate=1.4, peak=None, noise_seed=123,
    )
    spec = synth.render(patch)
    spec.validate()
    assert spec.pitched is False


def test_post_filter_rejects_lp_sweep():
    with pytest.raises(SampleConstraintError, match="post_filter"):
        synth.Patch(
            "X", (synth.WeightedLayer(synth.NoiseLayer()),), synth.OneShot(0.05),
            pitched=False, post_filter=synth.FilterSpec("lp_sweep", a_start=0.5, a_end=0.1),
        )


# ------------------------------------------------------------ decay_alpha（Patch 全体、フィルタ後）
def test_patch_level_decay_alpha_applies_after_layer_filter():
    """tuba/horn 型: フィルタ済み信号全体に一律の decay を掛ける（レイヤー個別 decay_alpha とは独立）。"""
    partials = ((1.0, 1.0, None), (2.0, 0.5, None))
    layer = synth.ToneLayer(partials, filter=synth.FilterSpec("lp", a=0.25))
    patch = synth.Patch(
        "Tuba", (synth.WeightedLayer(layer),), synth.OneShot(0.1),
        pitched=True, decay_alpha=7.0, saturate=None, peak=1.0,
    )
    spec = synth.render(patch)
    rate = dsp.sample_rate(24)
    f0 = hz(24)
    n = round(0.1 * rate)
    raw = [sum(w * math.sin(2 * math.pi * f0 * m * (i / rate)) for m, w, _ in partials) for i in range(n)]
    filtered = dsp.one_pole_lp(raw, 0.25)
    expected = [v * math.exp(-7.0 * i / rate) for i, v in enumerate(filtered)]
    m = max(abs(x) for x in expected)
    expected = [x / m for x in expected]
    got = _signed_samples(spec.data)
    for g, e in zip(got, expected):
        assert g == pytest.approx(round(e * 127), abs=1)


# ------------------------------------------------------------ attack_ms / saturate
def test_attack_ms_ramps_up_from_zero():
    patch = synth.Patch(
        "Horn", (synth.WeightedLayer(synth.ToneLayer(((1.0, 1.0, 9.0),))),),
        synth.OneShot(0.2), pitched=True, attack_ms=8.0, saturate=None, peak=1.0,
    )
    spec = synth.render(patch)
    xs = _signed_samples(spec.data)
    assert xs[0] == 0


def test_saturate_applies_tanh_bound():
    patch = synth.Patch(
        "Sat", (synth.WeightedLayer(synth.ToneLayer(((1.0, 1.0, None),))),),
        synth.OneShot(0.02), pitched=True, saturate=3.0, peak=1.0,
    )
    spec = synth.render(patch)
    xs = _signed_samples(spec.data)
    assert all(-128 <= v <= 127 for v in xs)


# ------------------------------------------------------------ Loop
def test_loop_finish_produces_valid_loop_spec():
    terms = tuple((6.0 * h, w, None) for h, w in ((1, 1.0), (3, 0.5), (5, 0.3)))
    patch = synth.Patch(
        "Pad", (synth.WeightedLayer(synth.ToneLayer(terms)),),
        synth.Loop(190, 60), pitched=True, volume=44,
    )
    spec = synth.render(patch)
    spec.validate()
    assert spec.loop == (30, 95)
    assert spec.length_words == 125


def test_loop_body_matches_seamless_terms():
    terms = ((6.0, 1.0, None), (12.0, 0.5, None))
    patch = synth.Patch(
        "Pad2", (synth.WeightedLayer(synth.ToneLayer(terms)),),
        synth.Loop(190, 60), pitched=True, saturate=None, peak=1.0,
    )
    spec = synth.render(patch)
    body_only = dsp.seamless_terms(190, [(6.0, 1.0), (12.0, 0.5)])
    m = max(abs(x) for x in body_only)
    expected_tail = [x / m for x in body_only]
    got = _signed_samples(spec.data)[60:]
    for g, e in zip(got, expected_tail):
        assert g == pytest.approx(round(e * 127), abs=1)


def test_loop_filter_uses_circular_wrapping_for_boundary_continuity():
    """Loop の lp フィルタは dsp.circular で包む（素朴な one_pole_lp は境界が不連続になりうる）。"""
    terms = ((6.0, 1.0, None), (18.0, 0.5, None))
    patch = synth.Patch(
        "Drone", (synth.WeightedLayer(synth.ToneLayer(terms, filter=synth.FilterSpec("lp", a=0.35))),),
        synth.Loop(760, 60), pitched=True, saturate=None, peak=1.0,
    )
    spec = synth.render(patch)
    xs = _signed_samples(spec.data)[30:]                 # loop body 部分（attack を除く）
    max_step = max(abs(xs[i + 1] - xs[i]) for i in range(len(xs) - 1))
    boundary_step = abs(xs[0] - xs[-1])
    assert boundary_step <= max_step + 2                  # PCM 量子化ぶんの余裕


def test_loop_filter_rejects_lp_sweep():
    layer = synth.ToneLayer(((6.0, 1.0, None),), filter=synth.FilterSpec("lp_sweep", a_start=0.6, a_end=0.2))
    patch = synth.Patch("X", (synth.WeightedLayer(layer),), synth.Loop(190, 60), pitched=True)
    with pytest.raises(SampleConstraintError, match="only valid as noise generation"):
        synth.render(patch)


# ------------------------------------------------------------ tail_fade_ms
def test_tail_fade_ms_ramps_last_samples_to_zero():
    rate = dsp.sample_rate(24)
    patch = synth.Patch(
        "Swoosh", (synth.WeightedLayer(synth.NoiseLayer(rise_power=2.2)),),
        synth.OneShot(0.3), pitched=False, tail_fade_ms=8000.0 / rate, saturate=None, peak=1.0,
    )
    spec = synth.render(patch)
    xs = _signed_samples(spec.data)
    assert xs[-1] == 0
    assert abs(xs[-2]) < abs(xs[-9])                      # 末尾へ向けて単調に絞られる

