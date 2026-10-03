"""Standard MIDI File の低レベル部品と読み戻し（DESIGN.md §7.7）。

MIDI を作るのは ``framework/realize/midi.py``（Score から直接）、構造検査は ``core/native_midi.py``。ここは両者が共有する
SMF のバイト列の部品（可変長数値・メタイベント・トラック）と、writer とは独立に SMF を読む ``parse_midi`` だけを持つ。
"""
from __future__ import annotations

import struct
from dataclasses import dataclass

from ..errors import PlanError

# ------------------------------------------------------------
# SMF の低レベル部品
# ------------------------------------------------------------

def _vlq(n: int) -> bytes:
    out = [n & 0x7F]
    n >>= 7
    while n:
        out.append(0x80 | (n & 0x7F))
        n >>= 7
    return bytes(reversed(out))


def _meta(kind: int, data: bytes) -> bytes:
    return bytes([0xFF, kind]) + _vlq(len(data)) + data


def _track(events: list[tuple[int, int, bytes]], end_tick: int = 0) -> bytes:
    """events: (midi_tick, 同 tick 内の順序, メッセージ)。note off → 制御 → note on の順に並べる。
    End of Track は ``end_tick``（最後のイベントより前なら最後のイベント）に置く。"""
    body = bytearray()
    now = 0
    for tick, _prio, msg in sorted(events, key=lambda e: (e[0], e[1])):
        body += _vlq(tick - now) + msg
        now = tick
    body += _vlq(max(0, end_tick - now)) + _meta(0x2F, b"")
    return b"MTrk" + struct.pack(">I", len(body)) + bytes(body)


OFF, CTRL, ON = 0, 1, 2


def _cc(ch: int, num: int, val: int) -> bytes:
    return bytes([0xB0 | ch, num, max(0, min(127, val))])


# ------------------------------------------------------------
# 変換
# ------------------------------------------------------------


# ------------------------------------------------------------
# 読み戻し（writer とは独立に SMF を読む）
# ------------------------------------------------------------

@dataclass
class ParsedMidi:
    format: int
    ppq: int
    tracks: list[list[tuple[int, bytes]]]           # 各トラックの (絶対 tick, メッセージ)


class MidiParseError(PlanError):
    pass


def parse_midi(data: bytes) -> ParsedMidi:
    if data[:4] != b"MThd" or len(data) < 14:
        raise MidiParseError("missing MThd")
    hlen, fmt, ntrks, ppq = struct.unpack(">IHHH", data[4:14])
    pos = 8 + hlen
    tracks = []
    for _ in range(ntrks):
        if data[pos:pos + 4] != b"MTrk":
            raise MidiParseError(f"missing MTrk at {pos}")
        (length,) = struct.unpack(">I", data[pos + 4:pos + 8])
        body = data[pos + 8:pos + 8 + length]
        if len(body) != length:
            raise MidiParseError("track truncated")
        pos += 8 + length
        events, p, now, status = [], 0, 0, 0
        while p < len(body):
            delta = 0
            while True:
                b = body[p]
                p += 1
                delta = (delta << 7) | (b & 0x7F)
                if not b & 0x80:
                    break
            now += delta
            if body[p] == 0xFF:
                n, q = 0, p + 2
                while True:
                    b = body[q]
                    q += 1
                    n = (n << 7) | (b & 0x7F)
                    if not b & 0x80:
                        break
                events.append((now, body[p:q + n]))
                p = q + n
                continue
            if body[p] & 0x80:
                status = body[p]
                p += 1
            size = 1 if status & 0xF0 in (0xC0, 0xD0) else 2
            events.append((now, bytes([status]) + body[p:p + size]))
            p += size
        tracks.append(events)
    if pos != len(data):
        raise MidiParseError(f"trailing bytes: {len(data) - pos}")
    return ParsedMidi(fmt, ppq, tracks)
