"""prefix.map（多音高の UTAU 音源。DESIGN.md §13.5.3.4）。

1 行: ``<音名><TAB><接頭辞><TAB><接尾辞>``。例 ``C3<TAB><TAB>_C3``（別名が ``あ_C3`` の版が C3 の音域）。
oto.ini の別名 = 接頭辞 + 基の別名（``あ``）+ 接尾辞。どれにも当たらない別名は「既定の高さ」の版とする。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

_NOTE = re.compile(r"^([A-Ga-g])([#b]?)(-?\d+)$")
_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


@dataclass(frozen=True)
class PrefixEntry:
    midi: int
    prefix: str
    suffix: str


def note_to_midi(name: str) -> Optional[int]:
    m = _NOTE.match(name.strip())
    if not m:
        return None
    pc = _PC[m.group(1).upper()] + {"#": 1, "b": -1, "": 0}[m.group(2)]
    return 12 * (int(m.group(3)) + 1) + pc          # C4 = 60


def parse(text: str) -> tuple[list[PrefixEntry], list[str]]:
    """(エントリ, 読めなかった行)。接頭辞も接尾辞も空の行は「既定」と区別できないので捨てる。"""
    out, bad = [], []
    for ln, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        parts = line.rstrip("\r\n").split("\t")
        midi = note_to_midi(parts[0]) if parts else None
        if midi is None or len(parts) < 2:
            bad.append(f"prefix.map line {ln}: cannot read {line.strip()!r}")
            continue
        prefix = parts[1]
        suffix = parts[2] if len(parts) > 2 else ""
        if prefix or suffix:
            out.append(PrefixEntry(midi, prefix, suffix))
    return out, bad


def split_alias(alias: str, entries: list[PrefixEntry]) -> tuple[str, Optional[int]]:
    """別名 → (基の別名, 音域の MIDI note｜None=既定)。最も長く当たる接頭辞＋接尾辞を採る。"""
    best: Optional[PrefixEntry] = None
    for e in entries:
        if alias.startswith(e.prefix) and alias.endswith(e.suffix) and len(alias) > len(e.prefix) + len(e.suffix):
            if best is None or len(e.prefix) + len(e.suffix) > len(best.prefix) + len(best.suffix):
                best = e
    if best is None:
        return alias, None
    return alias[len(best.prefix):len(alias) - len(best.suffix)], best.midi
