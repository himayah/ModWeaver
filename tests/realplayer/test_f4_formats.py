"""F4 の完了条件（FRAMEWORK_REDESIGN.md §16.2）のうち実プレイヤー（libopenmpt）を使うもの: I5（テンポと長さ）・
I6（音割れなし）・MP3（IT 経由）。3 つの試験移植ジャンル × S3M・XM・IT（MOD は F3 の再生確認を含む）。"""
from __future__ import annotations

import math

import pytest

from mod_weaver.core import native, render, writer
from mod_weaver.framework.compose import compose, resolve_plan
from mod_weaver.framework.realize.tracker import realize
from mod_weaver.framework.target import resolve
from tests.framework.realize.test_all_formats import GENRES
from tests.realplayer import decode, peak, requires_openmpt

pytestmark = requires_openmpt

CLIP_LIMIT = 10 ** (-0.5 / 20)          # I6: 最大振幅 ≤ −0.5 dBFS
CASES = [(name, fmt, ch) for name in GENRES for fmt, ch in
         (("mod", 4), ("mod", 8), ("s3m", None), ("xm", None), ("it", None)) if not (name == "march" and ch == 8)]


def _build(name, fmt, channels, seed=1):
    genre = GENRES[name]
    plan = resolve_plan(genre, seed=seed)
    score = compose(genre, plan, seed=seed, features=frozenset())
    target = resolve(fmt, channels, genre, seed=seed)
    return native.serialize(realize(genre, score, plan, target)), score


def _expected_seconds(score) -> float:
    """Score の時間軸の長さ（テンポ変化の無い曲）。1 step = ticks_per_step tick、1 tick = 2.5 / BPM 秒。"""
    assert not any(s.tempo for s in score.sections.values())
    return sum(score.sections[n].plan.steps * score.sections[n].plan.meter.ticks_per_step for n in score.order) \
        * 2.5 / score.bpm


@pytest.mark.parametrize("name, fmt, channels", CASES)
def test_i5_duration_matches_the_score(name, fmt, channels):
    data, score = _build(name, fmt, channels)
    played = decode(data, "." + fmt)
    assert played.stderr == ""
    expected = _expected_seconds(score)
    assert abs(played.seconds - expected) <= 0.005 * expected + 0.1, (played.seconds, expected)


@pytest.mark.parametrize("name, fmt, channels", CASES)
def test_i6_no_clipping(name, fmt, channels):
    data, _score = _build(name, fmt, channels)
    assert peak(data, "." + fmt) <= CLIP_LIMIT


@pytest.mark.parametrize("name", GENRES)
def test_extended_formats_are_audibly_present_on_every_channel_group(name):
    """音が出ていること（無音の曲になっていない）。"""
    for fmt in ("s3m", "xm", "it"):
        data, _score = _build(name, fmt, None)
        assert decode(data, "." + fmt).rms() > 200


def test_mp3_goes_through_it_at_320kbps():
    data, score = _build("march", "it", None)
    mp3 = render.render_mp3_from_it(data, "march")
    assert mp3[:3] == b"ID3"
    played = decode(mp3, ".mp3", demuxer=None)
    expected = _expected_seconds(score)
    assert abs(played.seconds - expected) <= 0.01 * expected + 0.5
    kbps = len(mp3) * 8 / played.seconds / 1000
    assert 300 <= kbps <= 330, kbps                     # 320 kbps（CBR）
    assert math.isfinite(played.rms()) and played.rms() > 200


def test_generate_reference_files_for_listening():
    """聴き比べ用に、3ジャンル × 全形式（MP3 は IT 経由）を ``output/f4-trial/`` に書き出す（F4 の完了条件の
    試聴はユーザーが行う。このテストは生成・検査が通ることだけを確認する。output/ は git の管理外）。"""
    import pathlib

    out = pathlib.Path("output") / "f4-trial"
    out.mkdir(parents=True, exist_ok=True)
    for name in GENRES:
        for fmt, channels in (("mod", 4), ("mod", 8), ("s3m", None), ("xm", None), ("it", None)):
            if name == "march" and channels == 8:
                continue
            data, _score = _build(name, fmt, channels, seed=42)
            tag = f"{channels}ch" if fmt == "mod" else "max"
            writer.write_file(out / f"{name}.{tag}.{fmt}", data)
        it_data, _score = _build(name, "it", None, seed=42)
        writer.write_file(out / f"{name}.max.mp3", render.render_mp3_from_it(it_data, name))
    assert len(list(out.iterdir())) >= 15
