"""``--lyrics`` の入力（文字列または ``@ファイル``）を区間ごとの音節列にする（VOCAL_DESIGN.md §4.1）。"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ..errors import LyricsError
from .lang import ja
from .phoneme import Syllable

_HEADER = re.compile(r"^\[([^\[\]]+)\]\s*$")


@dataclass(frozen=True)
class Lyrics:
    """``by_section``: 区間名 → 音節列（``None`` は休符）。``stream``: 区間名を指定しない歌詞（歌う区間へ出現順に流し込む）。"""
    by_section: dict[str, tuple[Optional[Syllable], ...]] = field(default_factory=dict)
    stream: tuple[Optional[Syllable], ...] = ()

    def check_sections(self, names) -> None:
        unknown = [n for n in self.by_section if n not in names]
        if unknown:
            raise LyricsError(f"lyrics section(s) not in this song: {', '.join(unknown)} (available: {', '.join(names)})")


def parse_lyrics(spec: str) -> Lyrics:
    if spec.startswith("@"):
        path = Path(spec[1:])
        try:
            text = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError) as e:
            raise LyricsError(f"cannot read lyrics file {path}: {e}") from e
        return parse_text(text)
    return Lyrics(stream=tuple(ja.parse(spec)))


def parse_text(text: str) -> Lyrics:
    sections: dict[str, list[Optional[Syllable]]] = {}
    stream: list[Optional[Syllable]] = []
    cur: Optional[str] = None
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = _HEADER.match(line)
        if m:
            cur = m.group(1).strip()
            sections.setdefault(cur, [])
            continue
        syls = ja.parse_line(line, n)
        if cur is None:
            if sections:
                raise LyricsError(f"line {n}: lyrics before the first [section]")
            stream.extend(syls)
        else:
            sections[cur].extend(syls)
    if stream and sections:
        raise LyricsError("lyrics file mixes unnamed lines and [section] blocks")
    return Lyrics({k: tuple(_trim(v)) for k, v in sections.items()}, tuple(_trim(stream)))


def _trim(items: list[Optional[Syllable]]) -> list[Optional[Syllable]]:
    out: list[Optional[Syllable]] = []
    for x in items:
        if x is None and (not out or out[-1] is None):
            continue
        out.append(x)
    while out and out[-1] is None:
        out.pop()
    return out
