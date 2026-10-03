"""共通フィクスチャ。"""
from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import os
import tempfile
from pathlib import Path

import pytest

def pytest_collection_modifyitems(config, items):
    """tests/realplayer/ の検査（実プレイヤーでの再生）に ``slow`` の印を付ける（DESIGN.md §10）。"""
    realplayer = Path(__file__).parent / "realplayer"
    for item in items:
        if realplayer in Path(str(item.fspath)).parents:
            item.add_marker(pytest.mark.slow)
