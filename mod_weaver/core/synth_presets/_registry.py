"""プリセットの登録簿（``synth_presets`` パッケージの全モジュールが共有する）。"""
from __future__ import annotations

from ..synth import Patch

PRESETS: dict[str, Patch] = {}
DESCRIPTIONS: dict[str, str] = {}


def register(key: str, patch: Patch, description: str) -> Patch:
    """プリセットを登録してそのまま返す。``X = register("x", Patch(...), "...")`` の形で使う。"""
    if key in PRESETS:
        raise ValueError(f"duplicate preset key: {key!r}")
    PRESETS[key] = patch
    DESCRIPTIONS[key] = description
    return patch


def find(keyword: str) -> list[str]:
    """説明文に ``keyword``（大小無視）を含むプリセットの key 一覧。"""
    kw = keyword.lower()
    return [k for k, d in DESCRIPTIONS.items() if kw in d.lower()]
