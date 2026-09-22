"""CP2〜CP5: Nostalgic 移植の旧実装との段階的等価性（設計書 §11.4）。"""
from __future__ import annotations

import contextlib
import io
import random
import subprocess
import sys
from pathlib import Path

import pytest

from mod_weaver import engine
from mod_weaver.core import writer
from mod_weaver.profiles import get_profile
from mod_weaver.profiles import nostalgic_samples as new_smp
from tests.conftest import REGRESSION_SEEDS, legacy_mod_bytes, load_reference

ROOT = Path(__file__).resolve().parents[2]
profile = get_profile("nostalgic")


# ---------------- CP2: サンプル ----------------

@pytest.mark.parametrize("name", ["kick", "snare", "hihat", "bass", "musicbox", "pad", "flute"])
def test_cp2_sample_bytes_match_legacy(name):
    ref = load_reference()
    assert getattr(new_smp, f"gen_{name}")() == getattr(ref, f"gen_{name}")()


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
def test_cp5_full_file_matches_legacy(seed):
    assert writer.serialize(engine.build_song(profile, seed)) == legacy_mod_bytes(seed)


@pytest.mark.parametrize("seed", REGRESSION_SEEDS[:5])
def test_cp5_generate_writes_identical_file(seed, tmp_path):
    out = tmp_path / "n.mod"
    result = engine.generate(profile, seed, out)
    assert out.read_bytes() == legacy_mod_bytes(seed)
    assert result.seed == seed and result.path == out
    assert not [i for i in result.issues if i.level != "INFO"]


@pytest.mark.parametrize("seed", [1, 42, 732501])
def test_cp5_toplevel_script_subprocess_identical(seed, tmp_path):
    """``modweaver.py`` は ``--genre`` 省略時、旧 ``twilight_pad.py`` とバイト単位で同一の出力を返す。"""
    out = tmp_path / "w.mod"
    r = subprocess.run(
        [sys.executable, str(ROOT / "modweaver.py"), "--seed", str(seed), "--output", str(out)],
        capture_output=True, text=True, cwd=tmp_path,
    )
    assert r.returncode == 0, r.stderr
    assert out.read_bytes() == legacy_mod_bytes(seed)
    assert f"python modweaver.py --genre nostalgic --seed {seed}" in r.stdout


def test_cp5_same_seed_twice_identical():
    a = writer.serialize(engine.build_song(profile, 5))
    b = writer.serialize(engine.build_song(profile, 5))
    assert a == b


def test_cp5_negative_seed_is_accepted():
    ref = load_reference()
    legacy = legacy_mod_bytes(-7)
    assert writer.serialize(engine.build_song(profile, -7)) == legacy
    assert ref is not None
