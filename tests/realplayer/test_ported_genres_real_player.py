"""移植したジャンル（``genres/``）の実プレイヤー検査（FRAMEWORK_REDESIGN.md §13.1 の I5・I6）。

全ジャンルについて、MOD（宣言された最大の予算）と IT で、再生した長さが Score の時間軸と一致し（I5。スウィングを含む）、
最大振幅が −0.5 dBFS 以下（I6）。XM・S3M は同じ Realizer の別の書き出しなので、F4 の検査（test_f4_formats.py）に任せる。
"""
from __future__ import annotations

import pytest

from mod_weaver.core import native
from mod_weaver.framework.compose import compose, resolve_plan
from mod_weaver.framework.realize.tracker import realize
from mod_weaver.framework.target import resolve
from tests.framework.test_ported_genres_all import IDS, PORTED, PORTED_F6, PORTED_F7, _genre
from tests.realplayer import decode, peak, requires_openmpt

pytestmark = requires_openmpt

CLIP_LIMIT = 10 ** (-0.5 / 20)


def _built(gid: str, fmt: str):
    genre = _genre(gid)
    plan = resolve_plan(genre, seed=1)
    score = compose(genre, plan, seed=1, features=frozenset())
    channels = max(genre.mod_channels) if fmt == "mod" else None
    data = native.serialize(realize(genre, score, plan, resolve(fmt, channels, genre, seed=1)))
    return data, score


def _expected_seconds(score) -> float:
    """Score の時間軸（テンポの変化を含む）。テンポの変化は、その step から後ろに効く（free-jazz のルバート）。"""
    bpm = score.bpm
    total = 0.0
    for name in score.order:
        sec = score.sections[name]
        tick = sec.plan.meter.ticks_per_step
        tempo = {t.step: t.bpm for t in sec.tempo}
        for step in range(sec.plan.steps):
            bpm = tempo.get(step, bpm)
            total += tick * 2.5 / bpm
    return total


@pytest.mark.parametrize("gid", sorted(PORTED & set(IDS)))
@pytest.mark.parametrize("fmt", ["mod", "it"])
def test_duration_matches_the_score_and_does_not_clip(gid, fmt):
    data, score = _built(gid, fmt)
    played = decode(data, "." + fmt)
    assert played.stderr == ""
    expected = _expected_seconds(score)
    assert abs(played.seconds - expected) <= 0.005 * expected + 0.2, (played.seconds, expected)
    assert played.rms() > 100                                  # 無音の曲になっていない
    assert peak(data, "." + fmt) <= CLIP_LIMIT


@pytest.mark.parametrize("batch, ids", [("f6-trial", PORTED_F6), ("f7-trial", PORTED_F7)])
def test_generate_reference_files_for_listening(batch, ids):
    """聴き比べ用に、ジャンルごとの MOD（最大の予算）・MIDI・MP3（IT 経由）を ``output/<batch>/`` に書き出す
    （試聴はユーザーが行う。このテストは生成・検査が通ることだけを確認する。output/ は git の管理外）。"""
    import pathlib

    from mod_weaver.core import render, writer
    from mod_weaver.framework.realize.midi import realize_midi

    out = pathlib.Path("output") / batch
    out.mkdir(parents=True, exist_ok=True)
    for gid in sorted(ids & set(IDS)):
        genre = _genre(gid)
        plan = resolve_plan(genre, seed=42)
        score = compose(genre, plan, seed=42, features=frozenset())
        mod = native.serialize(realize(genre, score, plan, resolve("mod", max(genre.mod_channels), genre, seed=42)))
        writer.write_file(out / f"{gid}.{max(genre.mod_channels)}ch.mod", mod)
        it = native.serialize(realize(genre, score, plan, resolve("it", None, genre, seed=42)))
        writer.write_file(out / f"{gid}.mp3", render.render_mp3_from_it(it, genre.title))
        writer.write_file(out / f"{gid}.mid", realize_midi(genre, score, plan, resolve("midi", None, genre, seed=42)))
    assert len(list(out.iterdir())) >= 3 * len(ids)
