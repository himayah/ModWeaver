"""CP2〜CP5: Nostalgic 移植の旧実装との段階的等価性（設計書 §11.4）。

CP2（サンプル波形）と CP5（完成ファイル）は、サンプル合成を core/synth.py の Patch 方式へ
移行したことで、もはやバイト単位の完全一致を目標としない（互換性を要求しない方針への変更）。
波形は構造的な近さ（長さ・ピーク振幅）のみ確認し、生成そのものが引き続き妥当な出力を作れることを
別途確認する。CP3（plan）・CP4（pattern の Cell 配置）は作曲ロジックを一切変更していないため、
今も旧実装とのバイト単位の等価性を保証する回帰として機能する。
"""
from __future__ import annotations

import random
import subprocess
import sys
from pathlib import Path

import pytest

from mod_weaver import engine
from mod_weaver.core import writer
from mod_weaver.core.verify import has_errors, verify
from mod_weaver.profiles import get_profile
from mod_weaver.profiles import nostalgic_samples as new_smp
from tests.conftest import REGRESSION_SEEDS, legacy_mod_bytes, load_reference

ROOT = Path(__file__).resolve().parents[2]
profile = get_profile("nostalgic")


# ---------------- CP2: サンプル ----------------

def _peak(data: bytes) -> int:
    return max(abs(b - 256 if b > 127 else b) for b in data)


@pytest.mark.parametrize("name", ["kick", "snare", "hihat", "bass", "musicbox", "pad", "flute"])
def test_cp2_sample_synthesis_is_structurally_close_to_legacy(name):
    """波形バイトの完全一致は求めない。長さ・ピーク振幅が旧実装と同程度であることだけ確認する。"""
    ref = load_reference()
    legacy = getattr(ref, f"gen_{name}")()
    new = getattr(new_smp, f"gen_{name}")().data
    assert abs(len(new) - len(legacy)) <= 4        # duration*rate の丸め方式の違いのみ許容
    assert abs(_peak(new) - _peak(legacy)) <= 2


def test_cp2_build_samples_layout_matches_legacy_table():
    specs = profile.build_samples()
    assert list(specs) == ["kick", "snare", "hihat", "bass", "musicbox", "pad", "flute"]   # sample 1..7
    expected = [("LoFiKick", 56), ("SoftSnare", 50), ("ClosedHH", 42), ("WarmBass", 60),
                ("MusicBox", 60), ("TwilightPad", 46), ("MellowFlute", 52)]
    assert [(s.name, s.volume) for s in specs.values()] == expected
    assert specs["pad"].loop == (0, len(specs["pad"].data) // 2)
    assert all(s.loop is None for k, s in specs.items() if k not in ("pad", "flute"))


# ---------------- CP3: plan() ----------------

def legacy_plan(seed):
    ref = load_reference()
    rng = random.Random(seed)
    idx_a = rng.randrange(len(ref.PROGRESSION_PRESETS))
    idx_b = (idx_a + rng.randint(1, len(ref.PROGRESSION_PRESETS) - 1)) % len(ref.PROGRESSION_PRESETS)
    bpm = rng.choice([88, 90, 92, 94, 96])
    return ref.PROGRESSION_PRESETS[idx_a], ref.PROGRESSION_PRESETS[idx_b], bpm


@pytest.mark.parametrize("seed", REGRESSION_SEEDS)
def test_cp3_plan_matches_legacy_procedure(seed):
    (name_a, prog_a), (name_b, prog_b), bpm = legacy_plan(seed)
    plan = profile.plan(random.Random(seed))
    assert plan.bpm == bpm
    assert plan.order == [0, 1, 2, 1, 3]
    labels = lambda pp: [s.chord.label for s in pp.slots]
    assert labels(plan.patterns[0]) == labels(plan.patterns[1]) == labels(plan.patterns[3]) == prog_a
    assert labels(plan.patterns[2]) == prog_b
    assert [p.kind for p in plan.patterns] == ["intro", "a", "b", "outro"]
    assert name_a in plan.summary[0] and name_b in plan.summary[1]


# ---------------- CP4: pattern ----------------

@pytest.mark.parametrize("seed", REGRESSION_SEEDS)
def test_cp4_patterns_match_legacy(seed):
    ref = load_reference()
    (_, prog_a), (_, prog_b), bpm = legacy_plan(seed)
    rng = random.Random(seed)   # 旧 build_procedural_mod と同じ消費順（先頭 3 回は plan 相当）
    rng.randrange(5); rng.randint(1, 4); rng.choice([88, 90, 92, 94, 96])
    legacy = [
        ref.build_procedural_pattern(rng, prog_a, bpm, is_intro=True),
        ref.build_procedural_pattern(rng, prog_a, bpm, is_intro=False, is_chorus=False),
        ref.build_procedural_pattern(rng, prog_b, bpm, is_intro=False, is_chorus=True),
        ref.build_procedural_pattern(rng, prog_a, bpm, is_outro=True),
    ]
    song = engine.build_song(profile, seed)
    assert len(song.patterns) == 4
    for i in range(4):
        assert song.patterns[i].serialize() == legacy[i], f"pattern {i}"


# ---------------- CP5: 全体 ----------------

@pytest.mark.parametrize("seed", REGRESSION_SEEDS)
def test_cp5_full_file_is_close_to_legacy_and_verifies_clean(seed):
    """サンプル波形が変わったためバイト完全一致は求めない。サイズが近く、検査が通ることを確認する。"""
    new = writer.serialize(engine.build_song(profile, seed))
    legacy = legacy_mod_bytes(seed)
    assert abs(len(new) - len(legacy)) <= 4 * 7     # 7 サンプル分の丸め誤差まで許容
    issues = verify(new, profile.channel_plan)
    assert not has_errors(issues)


@pytest.mark.parametrize("seed", REGRESSION_SEEDS[:5])
def test_cp5_generate_writes_valid_file(seed, tmp_path):
    out = tmp_path / "n.mod"
    result = engine.generate(profile, seed, out)
    assert out.exists() and out.stat().st_size > 0
    assert result.seed == seed and result.path == out
    assert not [i for i in result.issues if i.level != "INFO"]


@pytest.mark.parametrize("seed", [1, 42, 732501])
def test_cp5_toplevel_script_subprocess_writes_valid_file(seed, tmp_path):
    """``modweaver.py`` は ``--genre`` 省略時、nostalgic を生成する（旧 twilight_pad.py とのバイト一致は求めない）。"""
    out = tmp_path / "w.mod"
    r = subprocess.run(
        [sys.executable, str(ROOT / "modweaver.py"), "--seed", str(seed), "--output", str(out)],
        capture_output=True, text=True, cwd=tmp_path,
    )
    assert r.returncode == 0, r.stderr
    assert out.exists() and out.stat().st_size > 0
    assert f"python modweaver.py --genre nostalgic --seed {seed}" in r.stdout


def test_cp5_same_seed_twice_identical():
    a = writer.serialize(engine.build_song(profile, 5))
    b = writer.serialize(engine.build_song(profile, 5))
    assert a == b


def test_cp5_negative_seed_is_accepted():
    issues = verify(writer.serialize(engine.build_song(profile, -7)), profile.channel_plan)
    assert not has_errors(issues)
