"""F4 の完了条件のうち実プレイヤーを使わないもの（FRAMEWORK_REDESIGN.md §13.1 の I2・I3）。

3 つの試験移植ジャンルが、S3M・XM・IT（と MP3 の元になる IT）で、既定の予算と ``--channels`` を絞った予算の
どちらでも生成でき、検査に ERROR が無く、同じ入力から同じバイト列になる。MOD は F3 のテストが
（``test_ported_genres.py``）全予算を見ている。
"""
from __future__ import annotations

import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent / "genres"))

from march import MarchToy  # noqa: E402
from pop import PopToy  # noqa: E402
from racing_breaks import RacingBreaksToy  # noqa: E402

from mod_weaver.core import native  # noqa: E402
from mod_weaver.framework.compose import compose, resolve_plan  # noqa: E402
from mod_weaver.framework.realize.tracker import realize  # noqa: E402
from mod_weaver.framework.target import resolve  # noqa: E402

GENRES = {"pop": PopToy(), "racing-breaks": RacingBreaksToy(), "march": MarchToy()}
FORMATS = ("s3m", "xm", "it")
SEEDS = (1, 2, 3)


def _build(genre, fmt: str, seed: int, channels):
    plan = resolve_plan(genre, seed=seed)
    score = compose(genre, plan, seed=seed, features=frozenset())
    target = resolve(fmt, channels, genre, seed=seed)
    rs = realize(genre, score, plan, target)
    return rs, native.serialize(rs)


def _budgets(genre):
    return (None, min(genre.mod_channels))   # 既定の予算と、--channels の上限を mod_channels の最小値にした場合（I3）


@pytest.mark.parametrize("name", GENRES)
@pytest.mark.parametrize("fmt", FORMATS)
def test_generates_and_verifies_at_default_and_reduced_budgets(name, fmt):
    genre = GENRES[name]
    for seed in SEEDS:
        for channels in _budgets(genre):
            rs, data = _build(genre, fmt, seed, channels)
            errors = [i for i in native.verify(fmt, data) if i.level == "ERROR"]
            assert not errors, (name, fmt, seed, channels, errors)
            if channels is not None:
                assert rs.n_channels <= channels


@pytest.mark.parametrize("name", GENRES)
@pytest.mark.parametrize("fmt", FORMATS)
def test_output_is_deterministic(name, fmt):
    genre = GENRES[name]
    assert _build(genre, fmt, 2, None)[1] == _build(genre, fmt, 2, None)[1]


@pytest.mark.parametrize("fmt", FORMATS)
def test_wider_budget_gives_more_channels_than_mod_at_pop(fmt):
    """予算が大きい形式では、打楽器を分け、和音を声部に開く（§9.3）。MOD 8ch より厚い編成になる。"""
    rs, _data = _build(GENRES["pop"], fmt, 1, None)
    assert rs.n_channels > 8


@pytest.mark.parametrize("fmt", FORMATS)
def test_xm_variants_per_pan_only_in_xm(fmt):
    """XM は発音のたびにサンプルのパンへ戻るので lane のパンごとに別サンプル。他形式は共有する。"""
    rs, _data = _build(GENRES["pop"], fmt, 1, None)
    names = [s.name for s in rs.samples]
    assert any("@" in n for n in names) == (fmt == "xm")
    assert len(set(names)) == len(names)


def test_high_resolution_samples_for_xm_and_it_8bit_for_s3m():
    bits = {fmt: {s.bits for s in _build(GENRES["pop"], fmt, 1, None)[0].samples} for fmt in FORMATS}
    assert bits == {"s3m": {8}, "xm": {16}, "it": {16}}
    rs, _ = _build(GENRES["pop"], "s3m", 1, None)
    assert all(len(s.data) <= 64000 for s in rs.samples)
    assert all(abs(s.rate_hz - 44100) < 100 for s in rs.samples)   # 目標レート（ループは丸めで少しずれる）


# ---- 微分音・tune_cents の変種（§8.4）----

def _toy_with_tune(cents: float):
    import dataclasses

    from tests.framework.test_realize_mod import make_genre

    genre = make_genre()
    genre.instruments = {**genre.instruments, "lead": dataclasses.replace(genre.instruments["lead"],
                                                                         tune_cents=cents)}
    return genre


@pytest.mark.parametrize("fmt", FORMATS)
def test_tune_cents_makes_a_variant_with_scaled_playback_rate(fmt):
    plain, _ = _build(_toy_with_tune(0.0), fmt, 1, None)
    tuned, _ = _build(_toy_with_tune(30.0), fmt, 1, None)
    by_name = {s.name.split("+")[0].split("@")[0]: s for s in plain.samples}
    t = next(s for s in tuned.samples if s.name.startswith("lead+30c"))
    assert t.rate_hz == pytest.approx(by_name["lead"].rate_hz * 2 ** (30 / 1200), rel=1e-9)
    assert t.data == by_name["lead"].data           # 波形は同じで再生レートだけが違う
    assert not any("+" in s.name and "c" in s.name for s in plain.samples)


def test_mod_ignores_cents():
    """MOD は整数の tracker note に丸める（§16.5）ので、セントの変種は作らない。"""
    genre = _toy_with_tune(30.0)
    plan = resolve_plan(genre, seed=1)
    score = compose(genre, plan, seed=1, features=frozenset())
    rs = realize(genre, score, plan, resolve("mod", 8, genre, seed=1))
    assert not any("+30c" in s.name for s in rs.samples)
    assert any("+30c" in s.name for s in _build(genre, "s3m", 1, None)[0].samples)
