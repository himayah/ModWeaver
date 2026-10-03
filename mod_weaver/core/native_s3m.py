"""Scream Tracker 3 ``.s3m`` の書き出しと検査（DESIGN.md §7.4・§9.1）。``RealizedSong`` 用。

換算は Realizer が済ませてある（DESIGN.md §7 冒頭）ので、ここは形式の表記に並べ替えるだけ。バイナリの定数・補助・
パーサは ``s3m.py`` のものを使う。

- サンプル: 8-bit unsigned。**C2Spd ＝ 基準ノート C-4 での再生レート（``rate_hz``）**。1 サンプル 64000 byte 以下。
- note: 0 始まりの半音番号 k → ``((k // 12) << 4) | (k % 12)``。``NOTE_CUT`` は 254（^^^）。
- 音量はボリューム列、パンはヘッダのパンテーブル。エフェクトは ``Cmd`` の文字（A=1 … Z=26）。
"""
from __future__ import annotations

import struct

from ..errors import PlanError
from . import s3m
from .native import NOTE_CUT, NOTE_OFF, RCell, RealizedSong
from .verify import Issue, _Report

MAX_SAMPLE_BYTES = 64000
MIN_C2SPD, MAX_C2SPD = 1000, 65535     # 実用域の下限（F0 の注意点。DESIGN.md §9.2）と ST3 の上限
NOTE_CUT_BYTE = 254


def _note_byte(note: int) -> int:
    if note == NOTE_CUT:
        return NOTE_CUT_BYTE
    if note == NOTE_OFF:
        raise PlanError("S3M has no key-off (the realizer must use note cut)")
    return ((note // 12) << 4) | (note % 12)


def _command_byte(letter: str) -> int:
    return ord(letter) - ord("A") + 1


def _pack_cell(ch: int, c: RCell) -> bytes:
    what = 0
    body = bytearray()
    if c.note is not None or c.sample:
        what |= 0x20
        body += bytes([s3m.EMPTY_NOTE if c.note is None else _note_byte(c.note), c.sample])
    if c.vol is not None:
        what |= 0x40
        body.append(c.vol)
    if c.fx is not None:
        what |= 0x80
        body += bytes([_command_byte(c.fx[0]), c.fx[1]])
    if not what:
        return b""
    return bytes([what | ch]) + bytes(body)


def _pack_pattern(g) -> bytes:
    if g.rows != 64:
        raise PlanError(f"S3M patterns must have 64 rows: {g.rows}")
    body = bytearray()
    for r in range(g.rows):
        for ch in range(g.channels):
            body += _pack_cell(ch, g.get(r, ch))
        body.append(0)
    return struct.pack("<H", len(body) + 2) + bytes(body)


def _sample_header(spec, data_pointer: int) -> bytes:
    if spec.bits != 8:
        raise PlanError(f"S3M samples must be 8-bit: {spec.name!r} is {spec.bits}-bit")
    if len(spec.data) > MAX_SAMPLE_BYTES:
        raise PlanError(f"S3M sample {spec.name!r}: {len(spec.data)} bytes exceeds {MAX_SAMPLE_BYTES}")
    if spec.rate_hz is None:
        raise PlanError(f"sample {spec.name!r} has no rate_hz")
    c2spd = round(spec.rate_hz)
    if not 1 <= c2spd <= MAX_C2SPD:
        raise PlanError(f"S3M sample {spec.name!r}: C2Spd {c2spd} out of range")
    has_loop = spec.loop is not None
    start_words, len_words = spec.loop_header
    h = bytearray()
    h.append(1)
    h += bytes(12)
    h += bytes([(data_pointer >> 16) & 0xFF]) + struct.pack("<H", data_pointer & 0xFFFF)
    h += struct.pack("<I", len(spec.data))
    h += struct.pack("<I", start_words * 2 if has_loop else 0)
    h += struct.pack("<I", (start_words + len_words) * 2 if has_loop else 0)
    h += bytes([spec.volume, 0, 0, 1 if has_loop else 0])
    h += struct.pack("<I", c2spd)
    h += bytes(12)
    h += s3m._ascii(spec.name, 28, "sample name")
    h += b"SCRS"
    assert len(h) == s3m.SAMPLE_HEADER_SIZE, len(h)
    return bytes(h)


def serialize(rs: RealizedSong) -> bytes:
    n_channels = rs.n_channels
    if not 1 <= n_channels <= s3m.MAX_CHANNELS:
        raise PlanError(f"S3M channel count must be 1..{s3m.MAX_CHANNELS}: {n_channels}")
    if not rs.order or min(rs.order) < 0:
        raise PlanError(f"invalid order: {rs.order}")
    n_patterns = max(rs.order) + 1
    if n_patterns > min(len(rs.patterns), s3m.MAX_PATTERNS):
        raise PlanError(f"order refers to pattern {n_patterns - 1} but only {len(rs.patterns)} patterns exist "
                         f"(limit {s3m.MAX_PATTERNS})")
    if len(rs.samples) > s3m.MAX_INSTRUMENTS:
        raise PlanError(f"too many instruments: {len(rs.samples)} > {s3m.MAX_INSTRUMENTS}")
    orders = list(rs.order)
    if len(orders) % 2:
        orders.append(s3m.ORDER_END)
    if len(orders) > s3m.MAX_ORDERS:
        raise PlanError(f"too many orders: {len(orders)}")
    pans = rs.channel_pans

    out = bytearray()
    out += s3m._ascii(rs.title, 28, "title")
    out += bytes([0x1A, 16, 0, 0])
    out += struct.pack("<HHHHHH", len(orders), len(rs.samples), n_patterns, 0, s3m.CWT_V, s3m.FFI_UNSIGNED)
    out += b"SCRM"
    out += bytes([64, rs.initial_speed, rs.initial_bpm, s3m.STEREO | rs.mix_volume, 16, s3m.PAN_TABLE_ENABLED])
    out += bytes(8) + struct.pack("<H", 0)
    out += s3m._channel_settings(pans)
    assert len(out) == s3m.HEADER_SIZE
    out += bytes(orders)
    ins_ptr_pos = len(out)
    out += bytes(2 * len(rs.samples))
    pat_ptr_pos = len(out)
    out += bytes(2 * n_patterns)
    out += bytes(0x20 | (p >> 4) for p in pans) + bytes(32 - len(pans))

    header_ptrs = []
    for _ in rs.samples:
        header_ptrs.append(s3m._align16(out))
        out += bytes(s3m.SAMPLE_HEADER_SIZE)
    pattern_ptrs = []
    for g in rs.patterns[:n_patterns]:
        pattern_ptrs.append(s3m._align16(out))
        out += _pack_pattern(g)
    for ptr, spec in zip(header_ptrs, rs.samples):
        spec.validate()
        data_ptr = s3m._align16(out)
        out += bytes(b ^ 0x80 for b in spec.data)          # signed → unsigned
        out[ptr * 16:ptr * 16 + s3m.SAMPLE_HEADER_SIZE] = _sample_header(spec, data_ptr)

    struct.pack_into(f"<{len(header_ptrs)}H", out, ins_ptr_pos, *header_ptrs)
    struct.pack_into(f"<{len(pattern_ptrs)}H", out, pat_ptr_pos, *pattern_ptrs)
    return bytes(out)


# ============================================================
# 検査（読み戻しは s3m.parse_s3m。実プレイヤーの検査が正しさの本当の根拠）
# ============================================================

_DESCRIPTIONS = {
    "V01": "ファイル構造が読めない（パラポインタ・長さの不整合）",
    "V02": "マジックが不正",
    "V03": "order が不正",
    "V04": "サンプルヘッダが不正（音量・長さ・ループ・C2Spd の範囲）",
    "V05": "note が形式の音域外",
    "V06": "未定義のインストゥルメント番号を参照",
    "V07": "note を持つセルにインストゥルメント番号がない",
    "V08": "エフェクト／音量が不正（volume>64 または A00/T<32）",
    "V10": "order[0] の pattern にテンポ設定（Txx, xx≥32）がない",
    "V17": "サンプル長が上限（64000 byte）を超える",
    "V18": "C2Spd が実用域（1000 Hz 以上）を下回る",
}


def verify(data: bytes) -> list[Issue]:
    try:
        pm = s3m.parse_s3m(data)
    except (s3m.S3MParseError, struct.error, IndexError) as e:
        return [Issue("ERROR", "V01", str(e))]
    rep = _Report()
    if pm.magic != b"SCRM":
        rep.add("ERROR", "V02", f"magic={pm.magic!r}")
    real_orders = [o for o in pm.orders if o < 254]
    if not real_orders or any(o >= len(pm.patterns) for o in real_orders):
        rep.add("ERROR", "V03", f"orders={pm.orders}")
    for i, s in enumerate(pm.samples, start=1):
        if s.volume > 64 or len(s.data) != s.length or (s.flags & 1 and not s.loop_start < s.loop_end <= s.length) \
                or s.c2spd > MAX_C2SPD or s.c2spd == 0:
            rep.add("ERROR", "V04", f"sample {i}")
        if s.length > MAX_SAMPLE_BYTES:
            rep.add("ERROR", "V17", f"sample {i}: {s.length}")
        if 0 < s.c2spd < MIN_C2SPD:
            rep.add("WARN", "V18", f"sample {i}: {s.c2spd}")
    for p, pat in enumerate(pm.patterns):
        for r, row in enumerate(pat):
            for c, cell in enumerate(row):
                where = f"pattern {p} row {r} ch{c + 1}"
                has_note = cell.note not in (s3m.EMPTY_NOTE, NOTE_CUT_BYTE)
                if has_note and (cell.note >> 4 > 7 or (cell.note & 0x0F) >= 12):
                    rep.add("ERROR", "V05", f"{where}: note 0x{cell.note:02X}")
                if cell.instrument > len(pm.samples):
                    rep.add("ERROR", "V06", f"{where}: instrument {cell.instrument}")
                if has_note and not cell.instrument:
                    rep.add("ERROR", "V07", where)
                if cell.volume > 64 or (cell.command == _command_byte("A") and cell.info == 0) or \
                        (cell.command == _command_byte("T") and cell.info < 32):
                    rep.add("ERROR", "V08", where)
    if real_orders and real_orders[0] < len(pm.patterns):
        first = pm.patterns[real_orders[0]]
        if not any(c.command == _command_byte("T") and c.info >= 32 for row in first for c in row):
            rep.add("ERROR", "V10", f"pattern {real_orders[0]}")
    return rep.issues(_DESCRIPTIONS)
