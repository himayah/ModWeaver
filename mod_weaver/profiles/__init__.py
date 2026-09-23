"""ジャンルの仕組み（基底・登録簿・補助）。ジャンルそのものは ``mod_weaver/genres/`` にあり、import 時に自動登録される。"""
from __future__ import annotations

from .base import GenreProfile
from .registry import discover, get_profile, list_profiles, register_profile, resolve_id

discover()

__all__ = ["GenreProfile", "discover", "get_profile", "list_profiles", "register_profile", "resolve_id"]
