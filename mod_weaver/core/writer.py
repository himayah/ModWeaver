"""ProTracker ``M.K.`` シリアライザと原子的書込（設計書 §6.3）。

``WRITERS`` は出力フォーマット名→シリアライザの表。現在は ``"mod"`` のみ。
将来の別フォーマット（CORE_EXTENSION_DESIGN の EXT-6）は、この表への登録で追加できる。
"""
from __future__ import annotations

import os
import struct
from pathlib import Path
from typing import Callable, Union

from ..errors import OutputError, PlanError
from .model import Song

HEADER_SAMPLES = 31
ORDER_TABLE_SIZE = 128
TITLE_SIZE = 20
MAGIC = b"M.K."

XM_MAX_CHANNELS = 32   # EXT-6（未実装）: target_format != "mod" のプロファイルが宣言できる channel_plan の上限


def _ascii_bytes(text: str, limit: int, what: str) -> bytes:
    if len(text) > limit or not text.isascii():
        raise PlanError(f"{what} must be ASCII and <= {limit} chars: {text!r}")
    return text.encode("ascii")


def serialize(song: Song) -> bytes:
    """Song を ``M.K.`` 形式のバイト列へ変換する。"""
    if not 1 <= len(song.order) <= ORDER_TABLE_SIZE:
        raise PlanError(f"order length must be 1..{ORDER_TABLE_SIZE}: {len(song.order)}")
    if len(song.samples) > HEADER_SAMPLES:
        raise PlanError(f"too many samples: {len(song.samples)} > {HEADER_SAMPLES}")
    if min(song.order) < 0:
        raise PlanError(f"negative pattern number in order: {song.order}")
    n_patterns = max(song.order) + 1
    if n_patterns > len(song.patterns):
        raise PlanError(
            f"order refers to pattern {n_patterns - 1} but only {len(song.patterns)} patterns exist"
        )

    out = bytearray()
    out += _ascii_bytes(song.title, TITLE_SIZE, "title").ljust(TITLE_SIZE, b"\x00")

    for i in range(HEADER_SAMPLES):
        if i < len(song.samples):
            s = song.samples[i]
            s.validate()
            out += _ascii_bytes(s.name, 22, "sample name").ljust(22, b"\x00")
            out += struct.pack(">H", s.length_words)
            out += bytes([s.finetune & 0x0F])
            out += bytes([s.volume & 0xFF])
            out += struct.pack(">HH", *s.loop_header)
        else:
            out += b"\x00" * 30

    out += struct.pack(">BB", len(song.order), 0x7F)
    out += bytes(song.order + [0] * (ORDER_TABLE_SIZE - len(song.order)))
    out += MAGIC

    for pat in song.patterns[:n_patterns]:
        out += pat.serialize()
    for s in song.samples:
        out += s.data
    return bytes(out)


def write_file(path: Union[str, Path], data: bytes) -> None:
    """同一ディレクトリの一時ファイルへ書き、``os.replace`` で置換する。

    Windows でも既存ファイルを置換できる。失敗時は一時ファイルを削除して ``OutputError``。
    """
    target = Path(path)
    tmp = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    try:
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, target)
    except OSError as e:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise OutputError(f"cannot write {target}: {e}") from e


# 出力フォーマット名 → シリアライザ
WRITERS: dict[str, Callable[[Song], bytes]] = {"mod": serialize}
