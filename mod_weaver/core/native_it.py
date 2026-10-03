"""Impulse Tracker ``.it`` の書き出しと検査（DESIGN.md §7.5・§9.1）。``RealizedSong`` 用。

書き出しの要点:

- **楽器モード**（フラグの bit2）。1 サンプル＝1 楽器、キーボード表は全ノートをそのサンプルの同じノートに対応させる。
  NNA は Note Cut、DCT は無し。
- **16-bit サンプル**（サンプルのフラグ bit1、Cvt bit0=signed、非圧縮）。長さ・ループの単位は「サンプル数」。
- **C5Speed ＝ 基準ノート C-5（note 60）での再生レート（``rate_hz``）**。
- パンはヘッダのチャンネルパンだけ（サンプル・楽器の既定パンは使わない＝DfP の bit7 を立てない／「使わない」を立てる）。
- ``Instrument.release_s`` のあるサンプルだけ、音量エンベロープ（サステイン＋リリース）を有効にする。
  キーオフは ``===``（note 255）。``NOTE_CUT`` は ``^^^``（note 254）。
- 音量はボリューム列（0..64）。エフェクトは文字（A=1 … Z=26）。
"""
from __future__ import annotations

import struct
from typing import Optional

from ..errors import PlanError
from . import it
from .native import NOTE_CUT, NOTE_OFF, RCell, RealizedSong
from .verify import Issue, _Report

NOTE_CUT_BYTE = 254
NOTE_OFF_BYTE = 255
FLAG_INSTRUMENTS = 0x04
MIN_ROWS, MAX_ROWS = 32, 200
MIN_C5SPEED, MAX_C5SPEED = 1000, 0xFFFFFFFF
ENV_FLAG_ON, ENV_FLAG_SUSTAIN = 0x01, 0x04
ENV_SIZE = 82


def _note_byte(note: int) -> int:
    if note == NOTE_CUT:
        return NOTE_CUT_BYTE
    if note == NOTE_OFF:
        return NOTE_OFF_BYTE
    return note


def _command_byte(letter: str) -> int:
    return ord(letter) - ord("A") + 1


def _pack_cell(ch: int, c: RCell) -> bytes:
    mask = 0
    body = bytearray()
    if c.note is not None:
        mask |= 0x01
        body.append(_note_byte(c.note))
    if c.sample:
        mask |= 0x02
        body.append(c.sample)
    if c.vol is not None:
        mask |= 0x04
        body.append(c.vol)
    if c.fx is not None:
        mask |= 0x08
        body += bytes([_command_byte(c.fx[0]), c.fx[1]])
    if not mask:
        return b""
    return bytes([(ch + 1) | 0x80, mask]) + bytes(body)


def _pack_pattern(g) -> bytes:
    if not MIN_ROWS <= g.rows <= MAX_ROWS:
        raise PlanError(f"IT pattern rows must be {MIN_ROWS}..{MAX_ROWS}: {g.rows}")
    body = bytearray()
    for r in range(g.rows):
        for ch in range(g.channels):
            body += _pack_cell(ch, g.get(r, ch))
        body.append(0)
    return struct.pack("<HH4x", len(body), g.rows) + bytes(body)


def _sample_header(spec, data_offset: int) -> bytes:
    if spec.rate_hz is None:
        raise PlanError(f"sample {spec.name!r} has no rate_hz")
    c5 = round(spec.rate_hz)
    if c5 < 1:
        raise PlanError(f"IT sample {spec.name!r}: C5Speed {c5} out of range")
    bps = spec.bits // 8
    has_loop = spec.loop is not None
    start_words, len_words = spec.loop_header
    flags = it.SAMPLE_FLAG_HAS_DATA | (it.SAMPLE_FLAG_LOOP if has_loop else 0) | \
        (it.SAMPLE_FLAG_16BIT if spec.bits == 16 else 0)
    h = bytearray(b"IMPS")
    h += bytes(12)
    h += bytes([0, 64, flags, spec.volume])
    h += it._text(spec.name, 26, "sample name")
    h += bytes([it.CVT_SIGNED, 0])                       # Cvt: signed。DfP: パンは使わない
    h += struct.pack("<IIII", len(spec.data) // bps,
                     start_words * 2 // bps if has_loop else 0,
                     (start_words + len_words) * 2 // bps if has_loop else 0, c5)
    h += struct.pack("<III", 0, 0, data_offset)
    h += bytes(4)
    assert len(h) == it.SAMPLE_HEADER_SIZE, len(h)
    return bytes(h)


def _envelope(points: list[tuple[int, int]], flags: int, sustain: int) -> bytes:
    nodes = b"".join(struct.pack("<BH", v, t) for t, v in points).ljust(75, b"\x00")
    return bytes([flags, len(points), 0, 0, sustain, sustain]) + nodes + b"\x00"


def release_envelope(release_s: float, bpm: int) -> list[tuple[int, int]]:
    """点0（音量 64）でサステインし、ノートオフ後に ``release_s`` 秒で 0 へ落ちる。tick は曲の初期テンポで換算。"""
    ticks = max(1, round(release_s / (2.5 / bpm)))
    return [(0, 64), (ticks, 0)]


def _instrument_header(index: int, spec, release_s: Optional[float], bpm: int) -> bytes:
    h = bytearray(b"IMPI")
    h += bytes(12)
    h += bytes([0, 0, 0, 0])                              # 0, NNA=Note Cut, DCT=Off, DCA=Cut
    h += struct.pack("<H", 0)                             # fadeout
    h += bytes([0, 60, 128, 128 | 32, 0, 0])              # PPS, PPC, GbV, DfP(bit7=使わない), RV, RP
    h += struct.pack("<H", it.CWT_V)
    h += bytes([1, 0])                                    # NoS, unused
    h += it._text(spec.name, 26, "instrument name")
    h += bytes([0, 0, 0, 255]) + struct.pack("<H", 0)     # IFC, IFR, MCh, MPr, MIDIBnk
    h += b"".join(bytes([k, index]) for k in range(120))  # 全ノートをそのサンプルの同じノートへ
    if release_s is not None:
        h += _envelope(release_envelope(release_s, bpm), ENV_FLAG_ON | ENV_FLAG_SUSTAIN, 0)
    else:
        h += bytes(ENV_SIZE)
    h += bytes(ENV_SIZE) * 2                              # パン・ピッチのエンベロープは使わない
    h += bytes(4)
    assert len(h) == it.INSTRUMENT_HEADER_SIZE, len(h)
    return bytes(h)


def serialize(rs: RealizedSong) -> bytes:
    n_channels = rs.n_channels
    if not 1 <= n_channels <= it.MAX_CHANNELS:
        raise PlanError(f"IT channel count must be 1..{it.MAX_CHANNELS}: {n_channels}")
    if not rs.order or min(rs.order) < 0:
        raise PlanError(f"invalid order: {rs.order}")
    n_patterns = max(rs.order) + 1
    if n_patterns > min(len(rs.patterns), it.MAX_PATTERNS):
        raise PlanError(f"order refers to pattern {n_patterns - 1} but only {len(rs.patterns)} patterns exist "
                         f"(limit {it.MAX_PATTERNS})")
    n = len(rs.samples)
    if n > it.MAX_SAMPLES:
        raise PlanError(f"too many samples: {n} > {it.MAX_SAMPLES}")
    orders = list(rs.order) + [it.ORDER_END]

    out = bytearray(b"IMPM")
    out += it._text(rs.title, 26, "title")
    out += bytes([4, 16])
    out += struct.pack("<HHHHHHHH", len(orders), n, n, n_patterns, it.CWT_V, it.CMWT,
                       it.FLAG_STEREO | FLAG_INSTRUMENTS | it.FLAG_OLD_EFFECTS, 0)
    out += bytes([it.GLOBAL_VOLUME, rs.mix_volume, rs.initial_speed, rs.initial_bpm, 128, 0])
    out += struct.pack("<HII", 0, 0, 0)
    pans = [it.pan64(p) for p in rs.channel_pans]
    out += bytes(pans + [32 | it.CHANNEL_DISABLED] * (64 - len(pans)))
    out += bytes([64] * 64)
    assert len(out) == it.HEADER_SIZE
    out += bytes(orders)
    ins_ptr_pos = len(out)
    out += bytes(4 * n)
    smp_ptr_pos = len(out)
    out += bytes(4 * n)
    pat_ptr_pos = len(out)
    out += bytes(4 * n_patterns)

    ins_offsets = []
    for i, spec in enumerate(rs.samples, start=1):
        ins_offsets.append(len(out))
        out += _instrument_header(i, spec, rs.release_of(i), rs.initial_bpm)
    smp_offsets = []
    for _ in rs.samples:
        smp_offsets.append(len(out))
        out += bytes(it.SAMPLE_HEADER_SIZE)
    pat_offsets = []
    for g in rs.patterns[:n_patterns]:
        pat_offsets.append(len(out))
        out += _pack_pattern(g)
    for off, spec in zip(smp_offsets, rs.samples):
        spec.validate()
        data_offset = len(out)
        out += spec.data
        out[off:off + it.SAMPLE_HEADER_SIZE] = _sample_header(spec, data_offset)

    struct.pack_into(f"<{n}I", out, ins_ptr_pos, *ins_offsets)
    struct.pack_into(f"<{n}I", out, smp_ptr_pos, *smp_offsets)
    struct.pack_into(f"<{n_patterns}I", out, pat_ptr_pos, *pat_offsets)
    return bytes(out)


# ============================================================
# 検査（読み戻しは it.parse_it）
# ============================================================

_DESCRIPTIONS = {
    "V01": "ファイル構造が読めない（オフセット・長さの不整合）",
    "V02": "マジックが不正",
    "V03": "order が不正",
    "V04": "サンプルヘッダが不正（音量・長さ・ループ・Cvt）",
    "V05": "note が形式の音域（0..119・254・255）外",
    "V06": "未定義のインストゥルメント番号を参照",
    "V07": "note を持つセルにインストゥルメント番号がない",
    "V08": "エフェクト／音量が不正（volume>64 または A00/T<32）",
    "V10": "order[0] の pattern にテンポ設定（Txx, xx≥32）がない",
    "V18": "C5Speed が実用域（1000 Hz 以上）を下回る",
    "V19": "エンベロープが不正（点数・tick の単調増加・値の範囲）",
    "V21": "楽器ヘッダが不正（楽器モードのフラグ・キーボード表・NNA）",
    "V22": "pattern の row 数が 32..200 の外",
}


def verify(data: bytes) -> list[Issue]:
    try:
        pm = it.parse_it(data)
    except (it.ITParseError, struct.error, IndexError) as e:
        return [Issue("ERROR", "V01", str(e))]
    rep = _Report()
    if pm.magic != b"IMPM":
        rep.add("ERROR", "V02", f"magic={pm.magic!r}")
    if not pm.flags & FLAG_INSTRUMENTS:
        rep.add("ERROR", "V21", "instrument mode flag (bit2) is not set")
    real = [o for o in pm.orders if o < 254]
    if not real or any(o >= len(pm.patterns) for o in real):
        rep.add("ERROR", "V03", f"orders={pm.orders}")
    n = len(pm.samples)
    for i, s in enumerate(pm.samples, start=1):
        loop = s.flags & it.SAMPLE_FLAG_LOOP
        bps = 2 if s.flags & it.SAMPLE_FLAG_16BIT else 1
        if s.volume > 64 or len(s.data) != s.length * bps or not s.cvt & it.CVT_SIGNED or \
                (loop and not s.loop_begin < s.loop_end <= s.length):
            rep.add("ERROR", "V04", f"sample {i}")
        if 0 < s.c5speed < MIN_C5SPEED:
            rep.add("WARN", "V18", f"sample {i}: {s.c5speed}")
    if len(pm.instruments) != n:
        rep.add("ERROR", "V21", f"{len(pm.instruments)} instruments for {n} samples")
    for i, ins in enumerate(pm.instruments, start=1):
        if any(not 1 <= smp <= n for _note, smp in ins.keyboard) or ins.nna != 0:
            rep.add("ERROR", "V21", f"instrument {i}")
        if ins.vol_env_flags & ENV_FLAG_ON:
            ticks = [t for t, _v in ins.vol_env_points]
            if len(ticks) < 2 or ticks != sorted(set(ticks)) or any(v > 64 for _t, v in ins.vol_env_points):
                rep.add("ERROR", "V19", f"instrument {i}: {ins.vol_env_points}")
    for p, pat in enumerate(pm.patterns):
        if not MIN_ROWS <= len(pat) <= MAX_ROWS:
            rep.add("ERROR", "V22", f"pattern {p}: rows={len(pat)}")
        for r, row in enumerate(pat):
            for c, cell in enumerate(row):
                where = f"pattern {p} row {r} ch{c + 1}"
                has_note = 0 <= cell.note < NOTE_CUT_BYTE
                if cell.note >= 0 and not has_note and cell.note not in (NOTE_CUT_BYTE, NOTE_OFF_BYTE):
                    rep.add("ERROR", "V05", f"{where}: note {cell.note}")
                if has_note and cell.note > 119:
                    rep.add("ERROR", "V05", f"{where}: note {cell.note}")
                if cell.sample > n:
                    rep.add("ERROR", "V06", f"{where}: instrument {cell.sample}")
                if has_note and not cell.sample:
                    rep.add("ERROR", "V07", where)
                if cell.volume > 64 or (cell.command == _command_byte("A") and cell.info == 0) or \
                        (cell.command == _command_byte("T") and cell.info < 32):
                    rep.add("ERROR", "V08", where)
    if real and real[0] < len(pm.patterns):
        first = pm.patterns[real[0]]
        if not any(c.command == _command_byte("T") and c.info >= 32 for row in first for c in row):
            rep.add("ERROR", "V10", f"pattern {real[0]}")
    return rep.issues(_DESCRIPTIONS)
