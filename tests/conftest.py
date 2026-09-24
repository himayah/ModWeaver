"""共通フィクスチャ。凍結した旧実装（tests/reference/twilight_pad_v1.py）を読み込む補助を提供する。"""
from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import os
import tempfile
from pathlib import Path

import pytest

REFERENCE_PATH = Path(__file__).parent / "reference" / "twilight_pad_v1.py"
# 旧 twilight_pad.py の SHA-256（Phase 0 で凍結。誤編集の検知用）
REFERENCE_SHA256 = "b7f1aaef9df37622aef67c0d1053b23974bf6905ae51e792c8835b5cb2f3b2a0"

# 回帰用の固定 seed 20 件（DESIGN.md §10）: 固定 5 件 + 決定的に生成した 15 件
FIXED_SEEDS = [1, 42, 100000, 732501, 999999]


def _extra_seeds() -> list[int]:
    import random

    r = random.Random(20260922)
    return [r.randint(100000, 999999) for _ in range(15)]


REGRESSION_SEEDS = FIXED_SEEDS + _extra_seeds()


def load_reference():
    spec = importlib.util.spec_from_file_location("twilight_pad_v1", REFERENCE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_LEGACY_CACHE: dict[int, bytes] = {}


def legacy_mod_bytes(seed: int) -> bytes:
    """旧実装で seed から .mod を生成してバイト列を返す（結果はキャッシュ）。"""
    if seed not in _LEGACY_CACHE:
        ref = load_reference()
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "legacy.mod")
            with contextlib.redirect_stdout(io.StringIO()):
                ref.build_procedural_mod(path=path, seed=seed)
            _LEGACY_CACHE[seed] = Path(path).read_bytes()
    return _LEGACY_CACHE[seed]


def reference_sha256() -> str:
    return hashlib.sha256(REFERENCE_PATH.read_bytes()).hexdigest()


@pytest.fixture(scope="session")
def reference():
    return load_reference()


def pytest_collection_modifyitems(config, items):
    """tests/realplayer/ の検査（実プレイヤーでの再生）に ``slow`` の印を付ける（DESIGN.md §10）。"""
    realplayer = Path(__file__).parent / "realplayer"
    for item in items:
        if realplayer in Path(str(item.fspath)).parents:
            item.add_marker(pytest.mark.slow)
