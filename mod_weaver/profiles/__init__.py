"""可変層: ジャンル別プロファイル。import すると登録される。"""
from __future__ import annotations

from .base import GenreProfile
from .registry import get_profile, list_profiles, register_profile, resolve_id

from . import nostalgic, suspense_chase, suspense_slow  # noqa: F401  (登録のための import)

__all__ = ["GenreProfile", "get_profile", "list_profiles", "register_profile", "resolve_id"]
