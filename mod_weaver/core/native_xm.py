"""FastTracker II ``.xm`` の書き出しと検査（FRAMEWORK_REDESIGN.md §10.3・§10.5）。``RealizedSong`` 用。

旧 ``writer.serialize_xm``（``model.Song`` 用）は F8 まで並行して残る。違い:

- **音量はボリューム列**（``0x10 + vol``。旧: エフェクト ``Cxx``）。エフェクトの列は奏法に使える。
- **16-bit サンプル**対応: サンプルヘッダ type の bit4、データは 16-bit 語の差分（delta）符号化。
- 再生レート: 基準ノート C-4（XM note 49）で ``rate_hz`` になるよう relative note と finetune（1/128 半音）を書く
  （Amiga 周波数表のまま。D13）。
- パンはサンプル（instrument）のパン。Realizer が lane のパンごとに別サンプルを作る（``samples.sample_key``）ので、
  旧来のセルごとの ``Px`` は不要。
- ``Instrument.release_s`` のあるサンプルだけ、音量エンベロープ（サステイン＋リリース）を有効にする。
  キーオフはノート 97。
"""
from __future__ import annotations

import math
import struct
from typing import Optional

from ..errors import PlanError
from . import writer
from .native import NOTE_CUT, NOTE_OFF, RCell, RealizedSong
from .verify import Issue, ParseError, _Report, parse_xm

KEY_OFF = 97
BASE_RATE = 8363.0
MAX_CHANNELS = 32
MAX_PATTERNS = 256
ENV_MAX_POINTS = 12


def _effect_byte(letter: str) -> int:
    """XM のエフェクト番号: ``0``〜``9`` → 0..9、``A``〜``Z`` → 10..35。"""
    return int(letter, 36)


def _pack_cell(c: RCell) -> bytes:
    flags = 0
    body = bytearray()
    if c.note is not None:
        if c.note == NOTE_CUT:
            raise PlanError("XM has no note cut cell (the realizer must use volume 0)")
        flags |= 0x01
        body.append(KEY_OFF if c.note == NOTE_OFF else c.note + 1)
    if c.sample:
        flags |= 0x02
        body.append(c.sample)
    if c.vol is not None:
        flags |= 0x04
        body.append(0x10 + c.vol)
    if c.fx is not None:
        flags |= 0x08 | 0x10
        body += bytes([_effect_byte(c.fx[0]), c.fx[1]])
    return bytes([0x80 | flags]) + bytes(body)


def _pack_pattern(g) -> bytes:
    if not 1 <= g.rows <= 256:
        raise PlanError(f"XM pattern rows must be 1..256: {g.rows}")
    packed = b"".join(_pack_cell(g.get(r, ch)) for r in range(g.rows) for ch in range(g.channels))
    return struct.pack("<IBHH", 9, 0, g.rows, len(packed)) + packed


def delta_encode(data: bytes, bits: int) -> bytes:
    """差分符号化（直前のサンプルとの差。8-bit は 1 byte、16-bit は 2 byte のリトルエンディアン語）。"""
    if bits == 8:
        out = bytearray(len(data))
        prev = 0
        for i, b in enumerate(data):
            out[i] = (b - prev) & 0xFF
            prev = b
        return bytes(out)
    words = struct.unpack(f"<{len(data) // 2}H", data)
    out16, prev = [], 0
    for w in words:
        out16.append((w - prev) & 0xFFFF)
        prev = w
    return struct.pack(f"<{len(out16)}H", *out16)


def delta_decode(data: bytes, bits: int) -> list[int]:
    """``delta_encode`` の逆（符号付きの値の列）。"""
    if bits == 8:
        out, acc = [], 0
        for b in data:
            acc = (acc + b) & 0xFF
            out.append(acc - 256 if acc > 127 else acc)
        return out
    out, acc = [], 0
    for (w,) in struct.iter_unpack("<H", data):
        acc = (acc + w) & 0xFFFF
        out.append(acc - 65536 if acc > 32767 else acc)
    return out


def tuning(rate_hz: float) -> tuple[int, int]:
    """基準ノート C-4 で ``rate_hz`` になる (relative note, finetune)。finetune は 1/128 半音（-64..64）。"""
    total = round(12 * math.log2(rate_hz / BASE_RATE) * 128)
    rel = round(total / 128)
    fine = total - rel * 128
    if not -96 <= rel <= 95:
        raise PlanError(f"XM relative note {rel} out of range for rate {rate_hz:.0f} Hz")
    return rel, fine


def release_envelope(release_s: float, bpm: int) -> tuple[list[tuple[int, int]], int, int]:
    """(点の列, サステイン点, type)。点0（音量 64）でサステインし、キーオフ後に ``release_s`` 秒で 0 へ落ちる。
    tick は曲の初期テンポで換算（``2.5 / bpm`` 秒）。テンポが変わる曲では長さがずれる（§16.6）。"""
    ticks = max(1, round(release_s / (2.5 / bpm)))
    return [(0, 64), (ticks, 0)], 0, 0x03     # bit0=有効、bit1=サステイン


def _serialize_instrument(spec, release_s: Optional[float], bpm: int) -> bytes:
    spec.validate()
    if spec.rate_hz is None:
        raise PlanError(f"sample {spec.name!r} has no rate_hz")
    name = writer._xm_text(spec.name, 22, "instrument name")
    vol_pts: list[tuple[int, int]] = []
    sustain, env_type = 0, 0
    if release_s is not None:
        vol_pts, sustain, env_type = release_envelope(release_s, bpm)

    h = bytearray()
    h += struct.pack("<I", writer.XM_INSTRUMENT_HEADER_SIZE)
    h += name
    h += bytes([0])
    h += struct.pack("<H", 1)
    h += struct.pack("<I", writer.XM_SAMPLE_HEADER_SIZE)
    h += bytes(96)
    pts = b"".join(struct.pack("<HH", t, v) for t, v in vol_pts).ljust(48, b"\x00")
    h += pts
    h += bytes(48)
    h += bytes([len(vol_pts), 0, sustain, 0, 0, 0, 0, 0, env_type, 0])
    h += bytes(4)
    h += struct.pack("<H", 0)                       # fadeout（エンベロープで消すので使わない）
    h += struct.pack("<H", 0)
    assert len(h) == writer.XM_INSTRUMENT_HEADER_SIZE, len(h)

    rel, fine = tuning(spec.rate_hz)
    has_loop = spec.loop is not None
    start_words, len_words = spec.loop_header
    sample_type = (1 if has_loop else 0) | (0x10 if spec.bits == 16 else 0)
    sh = bytearray()
    sh += struct.pack("<I", len(spec.data))
    sh += struct.pack("<I", start_words * 2 if has_loop else 0)
    sh += struct.pack("<I", len_words * 2 if has_loop else 0)
    sh += bytes([spec.volume & 0xFF])
    sh += struct.pack("<b", fine)
    sh += bytes([sample_type, spec.pan & 0xFF])
    sh += struct.pack("<b", rel)
    sh += bytes([0])
    sh += writer._xm_text(spec.name, 22, "sample name")
    assert len(sh) == writer.XM_SAMPLE_HEADER_SIZE, len(sh)
    return bytes(h) + bytes(sh) + delta_encode(spec.data, spec.bits)


def serialize(rs: RealizedSong) -> bytes:
    n_channels = rs.n_channels
    if not 1 <= n_channels <= MAX_CHANNELS:
        raise PlanError(f"XM channel count must be 1..{MAX_CHANNELS}: {n_channels}")
    if not 1 <= len(rs.order) <= 256:
        raise PlanError(f"order length must be 1..256: {len(rs.order)}")
    if len(rs.samples) > writer.XM_MAX_INSTRUMENTS:
        raise PlanError(f"too many instruments: {len(rs.samples)} > {writer.XM_MAX_INSTRUMENTS}")
    n_patterns = max(rs.order) + 1
    if min(rs.order) < 0 or n_patterns > min(len(rs.patterns), MAX_PATTERNS):
        raise PlanError(f"order refers to pattern {n_patterns - 1} but only {len(rs.patterns)} patterns exist")

    out = bytearray()
    out += writer.XM_ID
    out += writer._xm_text(rs.title, 20, "title")
    out += bytes([0x1A])
    out += writer._xm_text(writer.XM_TRACKER_NAME, 20, "tracker name")
    out += struct.pack("<H", writer.XM_VERSION)
    out += struct.pack("<I", writer.XM_HEADER_SIZE)
    out += struct.pack("<HHHHH", len(rs.order), 0, n_channels, n_patterns, len(rs.samples))
    out += struct.pack("<H", 0)                      # flags: bit0=0 → Amiga 周波数表
    out += struct.pack("<HH", rs.initial_speed, rs.initial_bpm)
    out += bytes(rs.order) + bytes(writer.XM_ORDER_TABLE_SIZE - len(rs.order))
    for g in rs.patterns[:n_patterns]:
        out += _pack_pattern(g)
    for i, spec in enumerate(rs.samples, start=1):
        out += _serialize_instrument(spec, rs.release_of(i), rs.initial_bpm)
    return bytes(out)


# ============================================================
# 検査（読み戻しは verify.parse_xm）
# ============================================================

_DESCRIPTIONS = {
    "V01": "ファイルサイズが宣言内容と不一致",
    "V02": "マジックが不正",
    "V03": "曲長・order が不正",
    "V04": "サンプルヘッダが不正（音量・ループ・長さ・relative note）",
    "V05": "note が形式の音域（1..96・キーオフ 97）外",
    "V06": "未定義のインストゥルメント番号を参照",
    "V07": "note を持つセルにインストゥルメント番号がない",
    "V08": "ボリューム列／エフェクトの値が不正（F00・音量列が 0x10..0x50 以外）",
    "V10": "order[0] の pattern にテンポ設定（Fxx, param≥32）がない",
    "V11": "ループ境界の段差が大きい（クリックの恐れ）",
    "V12": "pattern 数が 256 を超える",
    "V13": "未使用のインストゥルメントがある",
    "V19": "エンベロープが不正（点数・tick の単調増加・値の範囲）",
    "V20": "チャンネル数・pattern の row 数が範囲外",
}


def _loop_step(values: list[int], bits: int) -> tuple[float, float]:
    peak = 127 if bits == 8 else 32767
    scale = 127.0 / peak                     # 8-bit 換算の段差（旧検査と同じ閾値の意味）
    max_diff = max((abs(values[i + 1] - values[i]) for i in range(len(values) - 1)), default=0) * scale
    return abs(values[0] - values[-1]) * scale, max(2.0, 1.5 * max_diff)


def verify(data: bytes) -> list[Issue]:
    try:
        pm = parse_xm(data)
    except ParseError as e:
        return [Issue("ERROR", "V01", str(e))]
    rep = _Report()
    if pm.magic != b"Extended Module: ":
        rep.add("ERROR", "V02", f"magic={pm.magic!r}")
    if not 1 <= pm.song_length <= len(pm.order):
        rep.add("ERROR", "V03", f"song_length={pm.song_length}")
    for i, p in enumerate(pm.order[:pm.song_length]):
        if p >= len(pm.patterns):
            rep.add("ERROR", "V03", f"order[{i}]={p} は実 pattern 数 {len(pm.patterns)} 以上")
    if pm.n_patterns > MAX_PATTERNS:
        rep.add("ERROR", "V12", f"pattern 数={pm.n_patterns}")
    if pm.size != pm.consumed:
        rep.add("ERROR", "V01", f"size={pm.size} consumed={pm.consumed}")
    if not 1 <= pm.n_channels <= MAX_CHANNELS:
        rep.add("ERROR", "V20", f"channels={pm.n_channels}")

    for i, inst in enumerate(pm.instruments, start=1):
        for s in inst.samples:
            if s.length == 0:
                continue
            bits = 16 if s.sample_type & 0x10 else 8
            looped = bool(s.sample_type & 0x03)
            if s.volume > 64 or not -96 <= s.relative_note <= 95 or (bits == 16 and s.length % 2):
                rep.add("ERROR", "V04", f"instrument {i}")
            if looped and s.loop_start + s.loop_length > s.length:
                rep.add("ERROR", "V04", f"instrument {i}: loop {s.loop_start}+{s.loop_length} > {s.length}")
            if looped and s.loop_length > 2 * (bits // 8) and s.loop_start + s.loop_length <= len(s.data):
                vals = delta_decode(s.data, bits)
                lo, hi = s.loop_start // (bits // 8), (s.loop_start + s.loop_length) // (bits // 8)
                step, limit = _loop_step(vals[lo:hi], bits)
                if step > limit:
                    rep.add("WARN", "V11", f"instrument {i}: 境界段差 {step:.1f} > 許容 {limit:.1f}")
        if inst.vol_type & 1:
            pts = inst.vol_points
            ticks = [t for t, _v in pts]
            if not 2 <= len(pts) <= ENV_MAX_POINTS or ticks != sorted(set(ticks)) or any(v > 64 for _t, v in pts):
                rep.add("ERROR", "V19", f"instrument {i}: {pts}")

    used: set[int] = set()
    defined = len(pm.instruments)
    for p, pat in enumerate(pm.patterns):
        if not 1 <= len(pat) <= 256:
            rep.add("ERROR", "V20", f"pattern {p}: rows={len(pat)}")
        for r, row in enumerate(pat):
            for c, cell in enumerate(row):
                where = f"pattern {p} row {r} ch{c + 1}"
                if cell.instrument:
                    used.add(cell.instrument)
                    if cell.instrument > defined:
                        rep.add("ERROR", "V06", f"{where}: instrument {cell.instrument}")
                if cell.note and not (1 <= cell.note <= 96 or cell.note == KEY_OFF):
                    rep.add("ERROR", "V05", f"{where}: note {cell.note}")
                if 1 <= cell.note <= 96 and cell.instrument == 0:
                    rep.add("ERROR", "V07", where)
                if cell.volume and not 0x10 <= cell.volume <= 0x50:
                    rep.add("ERROR", "V08", f"{where}: vol column 0x{cell.volume:02X}")
                if cell.effect == 0xF and cell.param == 0:
                    rep.add("ERROR", "V08", f"{where}: F00")
    if pm.order and pm.order[0] < len(pm.patterns):
        first = pm.patterns[pm.order[0]]
        if not any(c.effect == 0xF and c.param >= 32 for row in first for c in row):
            rep.add("ERROR", "V10", f"pattern {pm.order[0]}")
    for i, inst in enumerate(pm.instruments, start=1):
        if inst.samples and inst.samples[0].length > 0 and i not in used:
            rep.add("INFO", "V13", f"instrument {i}")
    return rep.issues(_DESCRIPTIONS)
