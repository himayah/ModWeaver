"""プロファイル登録簿（設計書 §7.4）。"""
from __future__ import annotations

from typing import TypeVar

from ..errors import ProfileNotFoundError
from .base import GenreProfile

T = TypeVar("T", bound=type)

PROFILE_REGISTRY: dict[str, type[GenreProfile]] = {}   # 正規 id → クラス
_ALIASES: dict[str, str] = {}                           # 別名 → 正規 id


def register_profile(cls: T) -> T:
    """``@register_profile`` でクラスを登録する（id・別名の重複は ValueError）。"""
    pid = cls.id
    if pid in PROFILE_REGISTRY or pid in _ALIASES:
        raise ValueError(f"duplicate profile id: {pid}")
    for a in cls.aliases:
        if a in PROFILE_REGISTRY or a in _ALIASES:
            raise ValueError(f"duplicate profile alias: {a}")
    PROFILE_REGISTRY[pid] = cls
    for a in cls.aliases:
        _ALIASES[a] = pid
    return cls


def resolve_id(name: str) -> str:
    """別名を正規 id に解決する。未登録は ProfileNotFoundError。"""
    if name in PROFILE_REGISTRY:
        return name
    if name in _ALIASES:
        return _ALIASES[name]
    raise ProfileNotFoundError(
        f"unknown genre: {name!r}. choices: {', '.join(sorted(PROFILE_REGISTRY))}"
        + (f" (aliases: {', '.join(f'{a}->{t}' for a, t in sorted(_ALIASES.items()))})" if _ALIASES else "")
    )


def get_profile(name: str) -> GenreProfile:
    return PROFILE_REGISTRY[resolve_id(name)]()


def list_profiles() -> list[type[GenreProfile]]:
    return [PROFILE_REGISTRY[k] for k in sorted(PROFILE_REGISTRY)]
