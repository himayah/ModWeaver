"""``Genre`` の登録簿とジャンルモジュールの自動検出（現行 ``profiles/registry.py`` と同じ仕組みを
``Genre`` 向けに用意したもの。FRAMEWORK_REDESIGN.md §2.4 の「そのまま残す」は現行の
``profiles/registry.py``（``GenreProfile`` 用）そのものを指し、これはその新しい方の相方になる。
移行が終わるまで2つの登録簿が並行する）。
"""
from __future__ import annotations

import importlib
import logging
import pkgutil
import sys
from typing import TypeVar

from ..errors import ProfileNotFoundError
from .genre import Genre

T = TypeVar("T", bound=type)

log = logging.getLogger(__name__)

RESERVED_NAMES = frozenset({"random", "r"})
CATEGORIES = ("mood", "genre", "style")

GENRE_REGISTRY: dict[str, type[Genre]] = {}
_ALIASES: dict[str, str] = {}


def register_genre(cls: T) -> T:
    """``@register_genre`` でクラスを登録する。検査は現行 ``register_profile`` と同じ。"""
    gid = getattr(cls, "id", None)
    if not isinstance(gid, str) or not gid:
        raise ValueError(f"{cls.__name__}: genre id must be a non-empty string")
    for attr in ("description", "description_en"):
        desc = getattr(cls, attr, None)
        if not isinstance(desc, str) or not desc.strip() or "\n" in desc or "\r" in desc:
            raise ValueError(f"{gid}: {attr} must be a non-empty single line")
    if getattr(cls, "category", None) not in CATEGORIES:
        raise ValueError(f"{gid}: category must be one of {', '.join(CATEGORIES)}: {getattr(cls, 'category', None)!r}")
    for name in (gid, *cls.aliases):
        if name in RESERVED_NAMES:
            raise ValueError(f"{gid}: {name!r} is reserved and cannot be a genre id or alias")
    if gid in GENRE_REGISTRY or gid in _ALIASES:
        raise ValueError(f"duplicate genre id: {gid}")
    for a in cls.aliases:
        if a in GENRE_REGISTRY or a in _ALIASES:
            raise ValueError(f"duplicate genre alias: {a}")
    GENRE_REGISTRY[gid] = cls
    for a in cls.aliases:
        _ALIASES[a] = gid
    return cls


def resolve_id(name: str) -> str:
    if name in GENRE_REGISTRY:
        return name
    if name in _ALIASES:
        return _ALIASES[name]
    raise ProfileNotFoundError(
        f"unknown genre: {name!r}. choices: {', '.join(sorted(GENRE_REGISTRY))}"
        + (f" (aliases: {', '.join(f'{a}->{t}' for a, t in sorted(_ALIASES.items()))})" if _ALIASES else "")
    )


def get_genre(name: str) -> Genre:
    return GENRE_REGISTRY[resolve_id(name)]()


def list_genres() -> list[type[Genre]]:
    return [GENRE_REGISTRY[k] for k in sorted(GENRE_REGISTRY)]


def discover(package: str) -> None:
    """``package`` 直下のモジュール（``_`` 始まり・サブパッケージを除く）をすべて import し、登録を起こす。

    現行 ``profiles.registry.discover()`` と同じ規則（壊れたモジュール・未登録のモジュールは警告のみ）。
    """
    pkg = importlib.import_module(package)
    for info in sorted(pkgutil.iter_modules(pkg.__path__), key=lambda i: i.name):
        if info.ispkg or info.name.startswith("_"):
            continue
        name = f"{package}.{info.name}"
        already = name in sys.modules
        try:
            importlib.import_module(name)
        except Exception as e:  # noqa: BLE001
            log.warning("genre module %s skipped: %s: %s", info.name, type(e).__name__, e)
            continue
        if not already and not any(c.__module__ == name for c in GENRE_REGISTRY.values()):
            log.warning("genre module %s registers no genre (@register_genre); ignored", info.name)
