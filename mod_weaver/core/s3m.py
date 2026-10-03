"""Scream Tracker 3 ``.s3m`` の定数・補助と読み戻し（DESIGN.md §7.4）。

書き出しは ``core/native_s3m.py``（Realizer の ``RealizedSong`` から）、構造検査もそちら。ここは両者が共有する形式の定数・
小さな補助と、writer とは独立に ``.s3m`` を読む ``parse_s3m`` だけを持つ。仕様の誤解（writer と parser が共有する誤り）は
検出できないため、tests/realplayer/ の libopenmpt による再生比較が正しさの本当の根拠。
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field

from ..errors import PlanError

MAX_CHANNELS = 16          # PCM チャンネルは L1..L8＋R1..R8 の 16 まで
MAX_INSTRUMENTS = 99
MAX_PATTERNS = 100
MAX_ORDERS = 256
HEADER_SIZE = 96
SAMPLE_HEADER_SIZE = 80
CWT_V = 0x1320             # Scream Tracker 3.20
FFI_UNSIGNED = 2
BASE_C2SPD = 8363
NOTE_T0_OCTAVE = 3         # t=0 → C-3（t=12 → C-4）
EMPTY_NOTE = 255
ORDER_END = 255
CHANNEL_UNUSED = 255
PAN_TABLE_ENABLED = 0xFC
STEREO = 0x80              # マスター音量の bit7。下位7bit は WriteOptions.mix_volume（ST3 の既定 48）


def _align16(buf: bytearray) -> int:
    """16 byte 境界までゼロ埋めし、その位置のパラポインタ（位置/16）を返す。"""
    buf += bytes(-len(buf) % 16)
    return len(buf) // 16


def _channel_settings(pans) -> bytes:
    """パンが中央以下のチャンネルは L1.., それ以外は R1.. に割り当てる（片側が埋まったら反対側）。
    実際の定位はパンテーブルが決める（ここは ST3 の PCM チャンネル番号の割当て）。"""
    free_left, free_right = list(range(0, 8)), list(range(8, 16))
    out = []
    for pan in pans:
        first, second = (free_left, free_right) if pan <= 128 else (free_right, free_left)
        out.append((first or second).pop(0))
    return bytes(out + [CHANNEL_UNUSED] * (32 - len(out)))


def _ascii(text: str, size: int, what: str) -> bytes:
    if len(text) >= size or not text.isascii():
        raise PlanError(f"{what} must be ASCII and < {size} chars: {text!r}")
    return text.encode("ascii").ljust(size, b"\x00")


@dataclass(frozen=True)
class ParsedS3MCell:
    note: int           # EMPTY_NOTE=255、それ以外は (octave<<4)|semitone
    instrument: int
    volume: int         # -1 = なし
    command: int
    info: int


@dataclass
class ParsedS3MSample:
    name: bytes
    length: int
    loop_start: int
    loop_end: int
    volume: int
    flags: int
    c2spd: int
    data: bytes = b""


@dataclass
class ParsedS3M:
    title: bytes
    magic: bytes
    orders: list[int]
    channel_settings: bytes
    pan_table: bytes
    initial_tempo: int
    samples: list[ParsedS3MSample] = field(default_factory=list)
    patterns: list[list[list[ParsedS3MCell]]] = field(default_factory=list)   # [pattern][row][ch]

    @property
    def channels(self) -> int:
        return sum(1 for b in self.channel_settings if b < 16)


class S3MParseError(PlanError):
    pass


def parse_s3m(data: bytes) -> ParsedS3M:
    if len(data) < HEADER_SIZE:
        raise S3MParseError(f"file too short: {len(data)}")
    ord_num, ins_num, pat_num = struct.unpack("<HHH", data[32:38])
    settings = data[64:96]
    pos = HEADER_SIZE
    orders = list(data[pos:pos + ord_num])
    pos += ord_num
    ins_ptrs = struct.unpack(f"<{ins_num}H", data[pos:pos + 2 * ins_num])
    pos += 2 * ins_num
    pat_ptrs = struct.unpack(f"<{pat_num}H", data[pos:pos + 2 * pat_num])
    pos += 2 * pat_num
    pm = ParsedS3M(data[0:28], data[44:48], orders, settings, data[pos:pos + 32], data[50])
    n_channels = pm.channels

    for ptr in ins_ptrs:
        h = data[ptr * 16:ptr * 16 + SAMPLE_HEADER_SIZE]
        if len(h) < SAMPLE_HEADER_SIZE:
            raise S3MParseError(f"sample header at {ptr * 16} truncated")
        data_ptr = (h[13] << 16) | struct.unpack("<H", h[14:16])[0]
        length, loop_start, loop_end = struct.unpack("<III", h[16:28])
        s = ParsedS3MSample(h[48:76], length, loop_start, loop_end, h[28], h[31], struct.unpack("<I", h[32:36])[0])
        s.data = data[data_ptr * 16:data_ptr * 16 + length]
        pm.samples.append(s)

    for ptr in pat_ptrs:
        p = ptr * 16 + 2
        rows = []
        for _ in range(64):
            row = [ParsedS3MCell(EMPTY_NOTE, 0, -1, 0, 0) for _ in range(n_channels)]
            while True:
                if p >= len(data):
                    raise S3MParseError("pattern data truncated")
                what = data[p]
                p += 1
                if what == 0:
                    break
                ch = what & 0x1F
                note, inst, vol, cmd, info = EMPTY_NOTE, 0, -1, 0, 0
                if what & 0x20:
                    note, inst = data[p], data[p + 1]
                    p += 2
                if what & 0x40:
                    vol = data[p]
                    p += 1
                if what & 0x80:
                    cmd, info = data[p], data[p + 1]
                    p += 2
                if ch < n_channels:
                    row[ch] = ParsedS3MCell(note, inst, vol, cmd, info)
            rows.append(row)
        pm.patterns.append(rows)
    return pm
