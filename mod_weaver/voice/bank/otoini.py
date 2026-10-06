"""oto.ini の読み込み（DESIGN.md §13.5.3.3）。

1 行: ``<wav名>=<別名>,<offset>,<consonant>,<cutoff>,<preutterance>,<overlap>``（ms）。
文字コードは UTF-8（厳密）→ cp932 の順に試す。
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ...errors import VoiceBankError


@dataclass(frozen=True)
class OtoEntry:
    wav: str
    alias: str
    offset: float
    consonant: float
    cutoff: float
    preutterance: float
    overlap: float


def decode(raw: bytes, name: str = "oto.ini") -> str:
    for enc in ("utf-8-sig", "cp932"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise VoiceBankError(f"{name}: cannot decode (tried UTF-8, cp932)")


def parse(text: str) -> tuple[list[OtoEntry], list[str]]:
    """(エントリ, 読めなかった行の説明)。別名が空のエントリは wav 名（拡張子なし）を別名にする（UTAU の流儀）。"""
    entries, bad = [], []
    for ln, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line or "=" not in line:
            if line:
                bad.append(f"line {ln}: no '='")
            continue
        wav, _, rest = line.partition("=")
        parts = rest.split(",")
        if len(parts) < 6:
            bad.append(f"line {ln}: expected 6 fields, got {len(parts)}")
            continue
        try:
            nums = [float(p) if p.strip() else 0.0 for p in parts[1:6]]
        except ValueError:
            bad.append(f"line {ln}: non-numeric field")
            continue
        alias = parts[0].strip() or Path(wav).stem
        entries.append(OtoEntry(wav.strip(), alias, *nums))
    return entries, bad


def load(path: Path) -> tuple[list[OtoEntry], list[str]]:
    try:
        raw = path.read_bytes()
    except OSError as e:
        raise VoiceBankError(f"{path}: {e}") from e
    return parse(decode(raw, path.name))


def is_cv_alias(alias: str) -> bool:
    """v1 が取り込める単独音（CV）の別名。VCV／CVVC（空白を含む・``-`` ``*`` で始まる）は除く。"""
    return bool(alias) and not any(c.isspace() for c in alias) and alias[0] not in "-*"


def detect_style(aliases: list[str]) -> str:
    """``hiragana`` | ``romaji`` | ``mixed`` | ``empty``。"""
    kana = sum(1 for a in aliases if any("぀" <= c <= "ヿ" for c in a))
    ascii_ = sum(1 for a in aliases if a.isascii())
    if not aliases:
        return "empty"
    if kana and kana >= len(aliases) * 0.8:
        return "hiragana"
    if ascii_ >= len(aliases) * 0.8:
        return "romaji"
    return "mixed"
