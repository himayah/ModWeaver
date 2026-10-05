"""取り込み済みバンクのキャッシュ（``<音源>/.modweaver/``。消してよい。VOCAL_DESIGN.md §5.3.1）。

``bank.json`` にメタデータ、``seg/<n>.pcm`` に各音節の 16-bit LE モノラル PCM。生成時は再解析せずこれを読む（NV-3）。
"""
from __future__ import annotations

import json
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ...errors import VoiceBankError

DIR = ".modweaver"
VERSION = 1


@dataclass(frozen=True)
class Syl:
    alias: str
    pcm: str                          # seg/ 以下のファイル名
    n: int                            # サンプル数
    pre: int                          # 母音の頭（サンプル）
    loop: Optional[tuple[int, int]]   # (開始, 長さ) サンプル単位。None はワンショット
    f0: Optional[float]
    peak: float                       # 取り込み時の母音部ピーク（正規化前）
    mismatch: Optional[float] = None


@dataclass(frozen=True)
class BankInfo:
    id: str
    lang: str
    rate: int
    home_hz: Optional[float]
    fingerprint: str
    credit: str
    credit_required: bool
    terms_url: str
    terms_checked: bool
    syllables: dict


def pcm_to_bytes(x: list[float]) -> bytes:
    return struct.pack(f"<{len(x)}h", *[max(-32768, min(32767, round(v * 32767))) for v in x])


def save(folder: Path, info: BankInfo, pcms: dict[str, list[float]], report: str) -> None:
    out = folder / DIR
    seg = out / "seg"
    seg.mkdir(parents=True, exist_ok=True)
    for old in seg.glob("*.pcm"):
        old.unlink()
    for name, x in pcms.items():
        (seg / name).write_bytes(pcm_to_bytes(x))
    d = {"version": VERSION, **{k: v for k, v in info.__dict__.items() if k != "syllables"},
         "syllables": {a: {k: (list(v) if isinstance(v, tuple) else v) for k, v in s.__dict__.items()}
                       for a, s in info.syllables.items()}}
    (out / "bank.json").write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "report.txt").write_text(report, encoding="utf-8")


def load_info(folder: Path) -> BankInfo:
    path = folder / DIR / "bank.json"
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
        if d.get("version") != VERSION:
            raise ValueError(f"version {d.get('version')} != {VERSION}")
        syls = {a: Syl(**{**s, "loop": tuple(s["loop"]) if s["loop"] else None}) for a, s in d["syllables"].items()}
        return BankInfo(d["id"], d["lang"], d["rate"], d["home_hz"], d["fingerprint"], d["credit"],
                        d["credit_required"], d["terms_url"], d["terms_checked"], syls)
    except (OSError, ValueError, KeyError, TypeError) as e:
        raise VoiceBankError(f"{path}: cache missing or broken ({e}); run 'modweaver_voice.py import' again") from e


def load_pcm(folder: Path, syl: Syl) -> bytes:
    path = folder / DIR / "seg" / syl.pcm
    try:
        data = path.read_bytes()
    except OSError as e:
        raise VoiceBankError(f"{path}: {e}") from e
    if len(data) != syl.n * 2:
        raise VoiceBankError(f"{path}: size mismatch (expected {syl.n * 2}, got {len(data)})")
    return data
