"""Impulse Tracker ``.it`` の定数・補助と読み戻し（DESIGN.md §7.5）。

書き出しは ``core/native_it.py``（Realizer の ``RealizedSong`` から。インストゥルメントモード・16-bit サンプル・エンベロープ）、
構造検査もそちら。ここは両者が共有する形式の定数・小さな補助と、writer とは独立に ``.it`` を読む ``parse_it`` だけを持つ。
正しさの本当の根拠は tests/realplayer/ の libopenmpt 再生比較。
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field

from ..errors import PlanError

MAX_CHANNELS = 64
MAX_SAMPLES = 99
MAX_PATTERNS = 200
HEADER_SIZE = 0xC0
SAMPLE_HEADER_SIZE = 0x50
PATTERN_HEADER_SIZE = 8
CWT_V = 0x0214
CMWT = 0x0214
ORDER_END = 255
FLAG_STEREO = 0x01
FLAG_OLD_EFFECTS = 0x10
GLOBAL_VOLUME = 128
CHANNEL_DISABLED = 0x80
SAMPLE_FLAG_HAS_DATA = 0x01
SAMPLE_FLAG_LOOP = 0x10
SAMPLE_FLAG_16BIT = 0x02
INSTRUMENT_HEADER_SIZE = 554
CVT_SIGNED = 0x01


def pan64(pan255: int) -> int:
    return round(pan255 * 64 / 255)


def _text(text: str, size: int, what: str) -> bytes:
    if len(text) >= size or not text.isascii():
        raise PlanError(f"{what} must be ASCII and < {size} chars: {text!r}")
    return text.encode("ascii").ljust(size, b"\x00")


# ============================================================
# 読み戻しと構造検査
# ============================================================

@dataclass(frozen=True)
class ParsedITCell:
    note: int           # -1 = なし
    sample: int
    volume: int         # -1 = なし
    command: int
    info: int


@dataclass
class ParsedITSample:
    name: bytes
    flags: int
    volume: int
    cvt: int
    dfp: int
    length: int
    loop_begin: int
    loop_end: int
    c5speed: int
    data: bytes = b""


@dataclass
class ParsedITInstrument:
    name: bytes
    nna: int
    fadeout: int
    dfp: int
    keyboard: list[tuple[int, int]]          # 120 組の (note, sample 番号)
    vol_env_flags: int = 0
    vol_env_points: list[tuple[int, int]] = field(default_factory=list)   # (tick, 値)
    vol_env_sustain: tuple[int, int] = (0, 0)


@dataclass
class ParsedIT:
    magic: bytes
    orders: list[int]
    flags: int
    initial_speed: int
    initial_tempo: int
    channel_pan: bytes
    samples: list[ParsedITSample] = field(default_factory=list)
    patterns: list[list[list[ParsedITCell]]] = field(default_factory=list)
    instruments: list[ParsedITInstrument] = field(default_factory=list)

    @property
    def channels(self) -> int:
        return sum(1 for b in self.channel_pan if not b & CHANNEL_DISABLED)


class ITParseError(PlanError):
    pass


def parse_it(data: bytes) -> ParsedIT:
    if len(data) < HEADER_SIZE:
        raise ITParseError(f"file too short: {len(data)}")
    ord_num, ins_num, smp_num, pat_num = struct.unpack("<4H", data[0x20:0x28])
    flags = struct.unpack("<H", data[0x2C:0x2E])[0]
    pos = HEADER_SIZE
    orders = list(data[pos:pos + ord_num])
    pos += ord_num
    ins_ptrs = struct.unpack(f"<{ins_num}I", data[pos:pos + 4 * ins_num])
    pos += 4 * ins_num
    smp_ptrs = struct.unpack(f"<{smp_num}I", data[pos:pos + 4 * smp_num])
    pos += 4 * smp_num
    pat_ptrs = struct.unpack(f"<{pat_num}I", data[pos:pos + 4 * pat_num])
    pm = ParsedIT(data[0:4], orders, flags, data[0x32], data[0x33], data[0x40:0x80])
    n = pm.channels

    for ptr in ins_ptrs:
        h = data[ptr:ptr + INSTRUMENT_HEADER_SIZE]
        if len(h) < INSTRUMENT_HEADER_SIZE or h[:4] != b"IMPI":
            raise ITParseError(f"bad instrument header at {ptr}")
        kb = [(h[0x40 + 2 * k], h[0x41 + 2 * k]) for k in range(120)]
        ef, num, _lb, _le, slb, sle = h[0x130:0x136]
        pts = [(struct.unpack("<H", h[0x137 + 3 * k:0x139 + 3 * k])[0], h[0x136 + 3 * k]) for k in range(min(num, 25))]
        pm.instruments.append(ParsedITInstrument(h[0x20:0x3A], h[0x11], struct.unpack("<H", h[0x14:0x16])[0],
                                                  h[0x19], kb, ef, pts, (slb, sle)))

    for ptr in smp_ptrs:
        h = data[ptr:ptr + SAMPLE_HEADER_SIZE]
        if len(h) < SAMPLE_HEADER_SIZE or h[:4] != b"IMPS":
            raise ITParseError(f"bad sample header at {ptr}")
        length, lb, le, c5 = struct.unpack("<IIII", h[0x30:0x40])
        data_ptr = struct.unpack("<I", h[0x48:0x4C])[0]
        s = ParsedITSample(h[0x14:0x2E], h[0x12], h[0x13], h[0x2E], h[0x2F], length, lb, le, c5)
        s.data = data[data_ptr:data_ptr + length * (2 if h[0x12] & SAMPLE_FLAG_16BIT else 1)]
        pm.samples.append(s)

    for ptr in pat_ptrs:
        length, rows = struct.unpack("<HH", data[ptr:ptr + 4])
        p = ptr + PATTERN_HEADER_SIZE
        end = p + length
        masks = [0] * 64
        grid = []
        for _ in range(rows):
            row = [ParsedITCell(-1, 0, -1, 0, 0) for _ in range(n)]
            while True:
                if p >= end:
                    raise ITParseError("pattern data truncated")
                cv = data[p]
                p += 1
                if cv == 0:
                    break
                ch = (cv - 1) & 63
                if cv & 0x80:
                    masks[ch] = data[p]
                    p += 1
                m = masks[ch]
                note, smp, vol, cmd, info = -1, 0, -1, 0, 0
                if m & 0x01:
                    note, p = data[p], p + 1
                if m & 0x02:
                    smp, p = data[p], p + 1
                if m & 0x04:
                    vol, p = data[p], p + 1
                if m & 0x08:
                    cmd, info = data[p], data[p + 1]
                    p += 2
                if ch < n:
                    row[ch] = ParsedITCell(note, smp, vol, cmd, info)
            grid.append(row)
        pm.patterns.append(grid)
    return pm
