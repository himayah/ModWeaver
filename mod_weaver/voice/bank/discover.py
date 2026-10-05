"""音源の置き場所の探索（VOCAL_DESIGN.md §5.3.1）。"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, Optional

from ...errors import VoiceBankError, VoiceNotFoundError
from . import cache

REPO_ROOT = Path(__file__).resolve().parents[3]


def search_dirs(voices_dir: Optional[str] = None, environ: Optional[dict] = None) -> list[Path]:
    """探索順: ``--voices-dir``（あればそこだけ）→ 環境変数 MODWEAVER_VOICES → <リポジトリ>/voices → ~/.modweaver/voices。"""
    if voices_dir:
        return [Path(voices_dir)]
    env = os.environ if environ is None else environ
    out = [Path(p) for p in env.get("MODWEAVER_VOICES", "").split(os.pathsep) if p]
    out += [REPO_ROOT / "voices", Path.home() / ".modweaver" / "voices"]
    return out


def installed(dirs: Iterable[Path]) -> dict[str, Path]:
    """取り込み済み（``.modweaver/bank.json`` がある）音源の ``id -> フォルダ``。先に見つかった方を優先。"""
    found: dict[str, Path] = {}
    for d in dirs:
        if not d.is_dir():
            continue
        for sub in sorted(p for p in d.iterdir() if p.is_dir()):
            if (sub / cache.DIR / "bank.json").is_file():
                try:
                    found.setdefault(cache.load_info(sub).id, sub)
                except VoiceBankError:
                    continue
    return found


def find(voice_id: str, dirs: Iterable[Path]) -> Path:
    found = installed(dirs)
    if voice_id not in found:
        raise VoiceNotFoundError(f"voice {voice_id!r} not found (searched: {', '.join(str(d) for d in dirs)})")
    return found[voice_id]
