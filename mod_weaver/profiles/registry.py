"""プロファイル登録簿（設計書 §7.4）とジャンルモジュールの自動検出（CLI_STAGE2_DESIGN §3）。"""
from __future__ import annotations

import importlib
import logging
import pkgutil
import sys
from typing import TypeVar

from ..errors import ProfileNotFoundError
from .base import GenreProfile

T = TypeVar("T", bound=type)

log = logging.getLogger(__name__)

GENRES_PACKAGE = "mod_weaver.genres"                    # ここに置いた .py がジャンルとして登録される
RESERVED_NAMES = frozenset({"random", "r"})             # --genre random / r（cli）が使うので id・別名にできない

PROFILE_REGISTRY: dict[str, type[GenreProfile]] = {}   # 正規 id → クラス
_ALIASES: dict[str, str] = {}                           # 別名 → 正規 id


def register_profile(cls: T) -> T:
    """``@register_profile`` でクラスを登録する（id・別名の重複・予約語、説明（日本語・英語）の欠落・複数行は ValueError）。"""
    pid = getattr(cls, "id", None)
    if not isinstance(pid, str) or not pid:
        raise ValueError(f"{cls.__name__}: profile id must be a non-empty string")
    for attr in ("description", "description_en"):
        desc = getattr(cls, attr, None)
        if not isinstance(desc, str) or not desc.strip() or "\n" in desc or "\r" in desc:
            raise ValueError(f"{pid}: {attr} must be a non-empty single line")
    for name in (pid, *cls.aliases):
        if name in RESERVED_NAMES:
            raise ValueError(f"{pid}: {name!r} is reserved and cannot be a profile id or alias")
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


def discover(package: str = GENRES_PACKAGE) -> None:
    """``package`` 直下のモジュール（``_`` 始まり・サブパッケージを除く）をすべて import し、登録を起こす。

    import に失敗したモジュールと、何も登録しないモジュールは WARNING を出して無視する（1ファイルの不具合で
    他のジャンルまで使えなくしない）。呼ぶ前から ``sys.modules`` にあるモジュールは登録の有無を検査しない:
    ジャンルモジュールを直接 import した場合、その途中で本関数が走り、登録前の import 途中のモジュールが返るため。
    """
    pkg = importlib.import_module(package)
    for info in sorted(pkgutil.iter_modules(pkg.__path__), key=lambda i: i.name):
        if info.ispkg or info.name.startswith("_"):
            continue
        name = f"{package}.{info.name}"
        already = name in sys.modules
        try:
            importlib.import_module(name)
        except Exception as e:  # noqa: BLE001  壊れたジャンルは飛ばして他を使えるようにする
            log.warning("genre module %s skipped: %s: %s", info.name, type(e).__name__, e)
            continue
        if not already and not any(c.__module__ == name for c in PROFILE_REGISTRY.values()):
            log.warning("genre module %s registers no genre (@register_profile); ignored", info.name)
