"""Scream Tracker 3 ``.s3m`` のシリアライザと構造検査（FORMAT_TEMPO_DESIGN §4.3）。

スコープは XM と同じ方針: 1 Instrument = 1 PCM サンプル、アドリブ音色・S3M 固有機能は使わない。

- 音高: tracker note t（0=ProTracker C-1＝period 856）→ ST3 の C-3（t=12＝period 428＝ST3 の C-4 が
  C2Spd で鳴る音）。note byte = ``(octave << 4) | semitone``。
- 音量: ``Cell.vol`` は volume column（S3M には Set Volume エフェクトが無い）。
- パン: ヘッダのチャンネル設定（L1..L8／R1..R8）＋パンテーブル（``dp=0xFC`` で有効）。
- サンプル: 8bit **unsigned**（``ffi=2``）。C2Spd は MOD finetune（1/8 半音単位）から計算する。
- エフェクト: ``core/effects.py`` の変換表。

``parse_s3m``/``verify_s3m`` は writer とは独立に読み戻す構造検査。仕様の誤解（writer と parser が共有する
誤り）は検出できないため、tests/realplayer/ の libopenmpt による再生比較が正しさの本当の根拠。
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field

from ..errors import PlanError
from . import effects
from .model import Cell, Pattern, SampleSpec, Song
from .pitch import NOTE_MAX

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
MASTER_VOLUME = 0x80 | 48  # bit7=ステレオ、下位7bit=マスター音量（ST3 の既定 48）


def note_byte(t: int) -> int:
    return ((t // 12 + NOTE_T0_OCTAVE) << 4) | (t % 12)


def c2spd(finetune: int) -> int:
    """MOD finetune（-8..7、1 単位＝1/8 半音）→ C2Spd（Hz）。"""
    return round(BASE_C2SPD * 2 ** (finetune / 96))


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


def _pack_cell(ch: int, cell: Cell) -> bytes:
    what = 0
    body = bytearray()
    if cell.note is not None or cell.sample:
        what |= 0x20
        body += bytes([EMPTY_NOTE if cell.note is None else note_byte(cell.note), cell.sample])
    if cell.vol is not None:
        what |= 0x40
        body.append(cell.vol)
    command, info = effects.to_st(cell.effect, cell.param)
    if command:
        what |= 0x80
        body += bytes([command, info])
    if not what:
        return b""
    return bytes([what | ch]) + bytes(body)


def _pack_pattern(pat: Pattern) -> bytes:
    if pat.rows != 64:
        raise PlanError(f"S3M patterns must have 64 rows: {pat.rows}")
    body = bytearray()
    for r in range(pat.rows):
        for c in range(pat.channels):
            body += _pack_cell(c, pat.get(r, c))
        body.append(0)                                  # row 終端
    return struct.pack("<H", len(body) + 2) + bytes(body)


def _sample_header(spec: SampleSpec, data_pointer: int) -> bytes:
    spec.validate()
    has_loop = spec.loop is not None
    start_words, len_words = spec.loop_header
    h = bytearray()
    h.append(1)                                          # type: PCM sample
    h += bytes(12)                                        # DOS filename（未使用）
    h += bytes([(data_pointer >> 16) & 0xFF]) + struct.pack("<H", data_pointer & 0xFFFF)
    h += struct.pack("<I", len(spec.data))
    h += struct.pack("<I", start_words * 2 if has_loop else 0)
    h += struct.pack("<I", (start_words + len_words) * 2 if has_loop else 0)
    h += bytes([spec.volume, 0, 0, 1 if has_loop else 0])   # volume, reserved, pack=0, flags(bit0=loop)
    h += struct.pack("<I", c2spd(spec.finetune))
    h += bytes(12)                                        # internal
    h += _ascii(spec.name, 28, "sample name")
    h += b"SCRS"
    assert len(h) == SAMPLE_HEADER_SIZE, len(h)
    return bytes(h)


def _ascii(text: str, size: int, what: str) -> bytes:
    if len(text) >= size or not text.isascii():
        raise PlanError(f"{what} must be ASCII and < {size} chars: {text!r}")
    return text.encode("ascii").ljust(size, b"\x00")


def serialize_s3m(song: Song, opts) -> bytes:
    """Song を ``.s3m`` 形式のバイト列へ変換する。``opts`` は ``formats.WriteOptions``。"""
    n_channels = song.patterns[0].channels if song.patterns else 0
    if not 1 <= n_channels <= MAX_CHANNELS:
        raise PlanError(f"S3M channel count must be 1..{MAX_CHANNELS}: {n_channels}")
    if not song.order or min(song.order) < 0:
        raise PlanError(f"invalid order: {song.order}")
    n_patterns = max(song.order) + 1
    if n_patterns > min(len(song.patterns), MAX_PATTERNS):
        raise PlanError(f"order refers to pattern {n_patterns - 1} but only {len(song.patterns)} patterns exist")
    if len(song.samples) > MAX_INSTRUMENTS:
        raise PlanError(f"too many instruments: {len(song.samples)} > {MAX_INSTRUMENTS}")
    orders = list(song.order)
    if len(orders) % 2:
        orders.append(ORDER_END)                          # ST3 は偶数個の order を前提にする
    if len(orders) > MAX_ORDERS:
        raise PlanError(f"too many orders: {len(orders)}")
    pans = opts.channel_pans

    out = bytearray()
    out += _ascii(song.title, 28, "title")
    out += bytes([0x1A, 16, 0, 0])
    out += struct.pack("<HHHHHH", len(orders), len(song.samples), n_patterns, 0, CWT_V, FFI_UNSIGNED)
    out += b"SCRM"
    out += bytes([64, 6, opts.initial_bpm, MASTER_VOLUME, 16, PAN_TABLE_ENABLED])
    out += bytes(8) + struct.pack("<H", 0)
    out += _channel_settings(pans)
    assert len(out) == HEADER_SIZE
    out += bytes(orders)
    ins_ptr_pos = len(out)
    out += bytes(2 * len(song.samples))
    pat_ptr_pos = len(out)
    out += bytes(2 * n_patterns)
    out += bytes(0x20 | (p >> 4) for p in pans) + bytes(32 - len(pans))   # パンテーブル（bit5=有効）

    # サンプルヘッダ → パターン → サンプルデータ（いずれも 16 byte 境界）
    header_ptrs = []
    for _ in song.samples:
        header_ptrs.append(_align16(out))
        out += bytes(SAMPLE_HEADER_SIZE)                   # データ位置が決まってから書き戻す
    pattern_ptrs = []
    for pat in song.patterns[:n_patterns]:
        pattern_ptrs.append(_align16(out))
        out += _pack_pattern(pat)
    for ptr, spec in zip(header_ptrs, song.samples):
        data_ptr = _align16(out)
        out += bytes(b ^ 0x80 for b in spec.data)          # signed → unsigned
        out[ptr * 16:ptr * 16 + SAMPLE_HEADER_SIZE] = _sample_header(spec, data_ptr)

    struct.pack_into(f"<{len(header_ptrs)}H", out, ins_ptr_pos, *header_ptrs)
    struct.pack_into(f"<{len(pattern_ptrs)}H", out, pat_ptr_pos, *pattern_ptrs)
    return bytes(out)


# ============================================================
# 読み戻しと構造検査
# ============================================================

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


_DESCRIPTIONS = {
    "V01": "ファイル構造が読めない（パラポインタ・長さの不整合）",
    "V02": "マジックが不正",
    "V03": "order が不正",
    "V04": "サンプルヘッダが不正",
    "V05": "note が本プロジェクトの音域（C-3..B-5）外",
    "V06": "未定義のインストゥルメント番号を参照",
    "V07": "note を持つセルにインストゥルメント番号がない",
    "V08": "エフェクト／音量が不正（volume>64 または A00/T<32）",
    "V09": "チャンネルに許可されていないインストゥルメント",
    "V10": "order[0] の pattern にテンポ設定（Txx, xx≥32）がない",
}


def verify_s3m(data: bytes, plan=None) -> list:
    from .verify import Issue, _Report

    try:
        pm = parse_s3m(data)
    except (S3MParseError, struct.error) as e:
        return [Issue("ERROR", "V01", str(e))]
    rep = _Report()
    if pm.magic != b"SCRM":
        rep.add("ERROR", "V02", f"magic={pm.magic!r}")
    real_orders = [o for o in pm.orders if o < 254]
    if not real_orders or any(o >= len(pm.patterns) for o in real_orders):
        rep.add("ERROR", "V03", f"orders={pm.orders}")
    for i, s in enumerate(pm.samples, start=1):
        if s.volume > 64 or len(s.data) != s.length or (s.flags & 1 and not s.loop_start < s.loop_end <= s.length):
            rep.add("ERROR", "V04", f"sample {i}")
    lo, hi = note_byte(0), note_byte(NOTE_MAX)
    for p, pat in enumerate(pm.patterns):
        for r, row in enumerate(pat):
            for c, cell in enumerate(row):
                where = f"pattern {p} row {r} ch{c + 1}"
                has_note = cell.note != EMPTY_NOTE
                if has_note and not (lo <= cell.note <= hi and (cell.note & 0x0F) < 12):
                    rep.add("ERROR", "V05", f"{where}: note 0x{cell.note:02X}")
                if cell.instrument > len(pm.samples):
                    rep.add("ERROR", "V06", f"{where}: instrument {cell.instrument}")
                if has_note and not cell.instrument:
                    rep.add("ERROR", "V07", where)
                if cell.volume > 64 or (cell.command == effects.letter("A") and cell.info == 0) or \
                        (cell.command == effects.letter("T") and cell.info < 32):
                    rep.add("ERROR", "V08", where)
                if plan is not None and cell.instrument and cell.instrument not in plan[c].allowed:
                    rep.add("ERROR", "V09", f"{where}: instrument {cell.instrument} on {plan[c].name}")
    if real_orders and real_orders[0] < len(pm.patterns):
        first = pm.patterns[real_orders[0]]
        if not any(c.command == effects.letter("T") and c.info >= 32 for row in first for c in row):
            rep.add("ERROR", "V10", f"pattern {real_orders[0]}")
    return rep.issues(_DESCRIPTIONS)
