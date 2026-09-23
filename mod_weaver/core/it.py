"""Impulse Tracker ``.it`` のシリアライザと構造検査（DESIGN.md §7.5）。

**サンプルモード**（インストゥルメント不使用）で書く。1 Instrument = 1 IT サンプル。エンベロープ・NNA 等の
IT 固有機能は使わない（XM/S3M と同じスコープ方針）。

- 音高: IT note = ``t + 48``（t=12＝period 428 → C-5＝C5Speed で鳴る音）。
- フラグ: stereo、Amiga slides（linear slides=0。MOD と同じ period 単位のスライド）、
  Old Effects=1（ビブラート深さ等を MOD 互換にする）。
- 音量: ``Cell.vol`` は volume column。パン: ヘッダのチャンネルパン＋明示パンのあるサンプルの既定パン（DfP）。
- サンプル: 8bit signed・非圧縮、C5Speed は MOD finetune から計算。
- エフェクト: ``core/effects.py`` の変換表（S3M と共通）。

``parse_it``/``verify_it`` は構造検査。正しさの本当の根拠は tests/realplayer/ の libopenmpt 再生比較。
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field

from ..errors import PlanError
from . import effects
from .model import Cell, Pattern, SampleSpec, Song
from .pitch import NOTE_MAX
from .s3m import c2spd as _c5speed   # 基準 8363Hz・finetune 1/8 半音の換算は S3M の C2Spd と同じ

MAX_CHANNELS = 64
MAX_SAMPLES = 99
MAX_PATTERNS = 200
HEADER_SIZE = 0xC0
SAMPLE_HEADER_SIZE = 0x50
PATTERN_HEADER_SIZE = 8
CWT_V = 0x0214
CMWT = 0x0214
NOTE_T0 = 48               # t=0 → IT note 48（C-4）、t=12 → 60（C-5）
ORDER_END = 255
FLAG_STEREO = 0x01
FLAG_OLD_EFFECTS = 0x10
GLOBAL_VOLUME = 128
MIX_VOLUME = 48
CHANNEL_DISABLED = 0x80
SAMPLE_FLAG_HAS_DATA = 0x01
SAMPLE_FLAG_LOOP = 0x10
CVT_SIGNED = 0x01
DFP_ENABLED = 0x80


def pan64(pan255: int) -> int:
    return round(pan255 * 64 / 255)


def c5speed(finetune: int) -> int:
    return _c5speed(finetune)


def _text(text: str, size: int, what: str) -> bytes:
    if len(text) >= size or not text.isascii():
        raise PlanError(f"{what} must be ASCII and < {size} chars: {text!r}")
    return text.encode("ascii").ljust(size, b"\x00")


def _pack_cell(ch: int, cell: Cell) -> bytes:
    mask = 0
    body = bytearray()
    if cell.note is not None:
        mask |= 0x01
        body.append(cell.note + NOTE_T0)
    if cell.sample:
        mask |= 0x02
        body.append(cell.sample)
    if cell.vol is not None:
        mask |= 0x04
        body.append(cell.vol)
    command, info = effects.to_st(cell.effect, cell.param)
    if command:
        mask |= 0x08
        body += bytes([command, info])
    if not mask:
        return b""
    return bytes([(ch + 1) | 0x80, mask]) + bytes(body)   # 毎回 mask を書く（前回値の再利用はしない）


def _pattern(pat: Pattern) -> bytes:
    if not 1 <= pat.rows <= 200:
        raise PlanError(f"IT pattern rows must be 1..200: {pat.rows}")
    body = bytearray()
    for r in range(pat.rows):
        for c in range(pat.channels):
            body += _pack_cell(c, pat.get(r, c))
        body.append(0)                                    # row 終端
    return struct.pack("<HH4x", len(body), pat.rows) + bytes(body)


def _sample_header(spec: SampleSpec, data_offset: int, explicit_pan: bool) -> bytes:
    spec.validate()
    has_loop = spec.loop is not None
    start_words, len_words = spec.loop_header
    h = bytearray(b"IMPS")
    h += bytes(12)                                        # DOS filename
    h += bytes([0, 64])                                   # reserved, global volume
    h.append(SAMPLE_FLAG_HAS_DATA | (SAMPLE_FLAG_LOOP if has_loop else 0))
    h.append(spec.volume)
    h += _text(spec.name, 26, "sample name")
    h.append(CVT_SIGNED)
    h.append(DFP_ENABLED | pan64(spec.pan) if explicit_pan else pan64(spec.pan))
    h += struct.pack("<IIII", len(spec.data),
                     start_words * 2 if has_loop else 0,
                     (start_words + len_words) * 2 if has_loop else 0,
                     c5speed(spec.finetune))
    h += struct.pack("<III", 0, 0, data_offset)           # sustain loop（未使用）、sample pointer
    h += bytes(4)                                          # auto vibrato（未使用）
    assert len(h) == SAMPLE_HEADER_SIZE, len(h)
    return bytes(h)


def serialize_it(song: Song, opts) -> bytes:
    """Song を ``.it`` 形式のバイト列へ変換する。``opts`` は ``formats.WriteOptions``。"""
    n_channels = song.patterns[0].channels if song.patterns else 0
    if not 1 <= n_channels <= MAX_CHANNELS:
        raise PlanError(f"IT channel count must be 1..{MAX_CHANNELS}: {n_channels}")
    if not song.order or min(song.order) < 0:
        raise PlanError(f"invalid order: {song.order}")
    n_patterns = max(song.order) + 1
    if n_patterns > min(len(song.patterns), MAX_PATTERNS):
        raise PlanError(f"order refers to pattern {n_patterns - 1} but only {len(song.patterns)} patterns exist")
    if len(song.samples) > MAX_SAMPLES:
        raise PlanError(f"too many samples: {len(song.samples)} > {MAX_SAMPLES}")
    orders = list(song.order) + [ORDER_END]

    out = bytearray(b"IMPM")
    out += _text(song.title, 26, "title")
    out += bytes([4, 16])                                  # row highlight（拍・小節の目安表示）
    out += struct.pack("<HHHHHHHH", len(orders), 0, len(song.samples), n_patterns, CWT_V, CMWT,
                       FLAG_STEREO | FLAG_OLD_EFFECTS, 0)
    out += bytes([GLOBAL_VOLUME, MIX_VOLUME, 6, opts.initial_bpm, 128, 0])
    out += struct.pack("<HII", 0, 0, 0)                     # message length/offset, reserved
    pans = [pan64(p) for p in opts.channel_pans]
    out += bytes(pans + [32 | CHANNEL_DISABLED] * (64 - len(pans)))
    out += bytes([64] * 64)
    assert len(out) == HEADER_SIZE
    out += bytes(orders)
    smp_ptr_pos = len(out)
    out += bytes(4 * len(song.samples))
    pat_ptr_pos = len(out)
    out += bytes(4 * n_patterns)

    explicit = [s.pan != 128 for s in song.samples]
    header_offsets = []
    for _ in song.samples:
        header_offsets.append(len(out))
        out += bytes(SAMPLE_HEADER_SIZE)                   # データ位置が決まってから書き戻す
    pattern_offsets = []
    for pat in song.patterns[:n_patterns]:
        pattern_offsets.append(len(out))
        out += _pattern(pat)
    for off, spec, exp in zip(header_offsets, song.samples, explicit):
        data_offset = len(out)
        out += spec.data                                    # signed 8bit のまま
        out[off:off + SAMPLE_HEADER_SIZE] = _sample_header(spec, data_offset, exp)

    struct.pack_into(f"<{len(header_offsets)}I", out, smp_ptr_pos, *header_offsets)
    struct.pack_into(f"<{len(pattern_offsets)}I", out, pat_ptr_pos, *pattern_offsets)
    return bytes(out)


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
class ParsedIT:
    magic: bytes
    orders: list[int]
    flags: int
    initial_speed: int
    initial_tempo: int
    channel_pan: bytes
    samples: list[ParsedITSample] = field(default_factory=list)
    patterns: list[list[list[ParsedITCell]]] = field(default_factory=list)

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
    pos += ord_num + 4 * ins_num
    smp_ptrs = struct.unpack(f"<{smp_num}I", data[pos:pos + 4 * smp_num])
    pos += 4 * smp_num
    pat_ptrs = struct.unpack(f"<{pat_num}I", data[pos:pos + 4 * pat_num])
    pm = ParsedIT(data[0:4], orders, flags, data[0x32], data[0x33], data[0x40:0x80])
    n = pm.channels

    for ptr in smp_ptrs:
        h = data[ptr:ptr + SAMPLE_HEADER_SIZE]
        if len(h) < SAMPLE_HEADER_SIZE or h[:4] != b"IMPS":
            raise ITParseError(f"bad sample header at {ptr}")
        length, lb, le, c5 = struct.unpack("<IIII", h[0x30:0x40])
        data_ptr = struct.unpack("<I", h[0x48:0x4C])[0]
        s = ParsedITSample(h[0x14:0x2E], h[0x12], h[0x13], h[0x2E], h[0x2F], length, lb, le, c5)
        s.data = data[data_ptr:data_ptr + length]
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


_DESCRIPTIONS = {
    "V01": "ファイル構造が読めない（オフセット・長さの不整合）",
    "V02": "マジックが不正",
    "V03": "order が不正",
    "V04": "サンプルヘッダが不正",
    "V05": "note が本プロジェクトの音域（C-4..B-6）外",
    "V06": "未定義のサンプル番号を参照",
    "V07": "note を持つセルにサンプル番号がない",
    "V08": "エフェクト／音量が不正（volume>64 または A00/T<32）",
    "V09": "チャンネルに許可されていないサンプル",
    "V10": "order[0] の pattern にテンポ設定（Txx, xx≥32）がない",
}


def verify_it(data: bytes, plan=None) -> list:
    from .verify import Issue, _Report

    try:
        pm = parse_it(data)
    except (ITParseError, struct.error, IndexError) as e:
        return [Issue("ERROR", "V01", str(e))]
    rep = _Report()
    if pm.magic != b"IMPM":
        rep.add("ERROR", "V02", f"magic={pm.magic!r}")
    real = [o for o in pm.orders if o < 254]
    if not real or any(o >= len(pm.patterns) for o in real):
        rep.add("ERROR", "V03", f"orders={pm.orders}")
    for i, s in enumerate(pm.samples, start=1):
        loop = s.flags & SAMPLE_FLAG_LOOP
        if s.volume > 64 or len(s.data) != s.length or (loop and not s.loop_begin < s.loop_end <= s.length):
            rep.add("ERROR", "V04", f"sample {i}")
    for p, pat in enumerate(pm.patterns):
        for r, row in enumerate(pat):
            for c, cell in enumerate(row):
                where = f"pattern {p} row {r} ch{c + 1}"
                if cell.note >= 0 and not NOTE_T0 <= cell.note <= NOTE_T0 + NOTE_MAX:
                    rep.add("ERROR", "V05", f"{where}: note {cell.note}")
                if cell.sample > len(pm.samples):
                    rep.add("ERROR", "V06", f"{where}: sample {cell.sample}")
                if cell.note >= 0 and not cell.sample:
                    rep.add("ERROR", "V07", where)
                if cell.volume > 64 or (cell.command == effects.letter("A") and cell.info == 0) or \
                        (cell.command == effects.letter("T") and cell.info < 32):
                    rep.add("ERROR", "V08", where)
                if plan is not None and cell.sample and cell.sample not in plan[c].allowed:
                    rep.add("ERROR", "V09", f"{where}: sample {cell.sample} on {plan[c].name}")
    if real and real[0] < len(pm.patterns):
        first = pm.patterns[real[0]]
        if not any(c.command == effects.letter("T") and c.info >= 32 for row in first for c in row):
            rep.add("ERROR", "V10", f"pattern {real[0]}")
    return rep.issues(_DESCRIPTIONS)
