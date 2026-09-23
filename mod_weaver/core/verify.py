"""独立パーサ ``parse_mod`` と構造検査 ``verify``（設計書 §6.4）。

書込側（``writer`` / ``model``）とは独立に、バイト列を ``struct`` で直接読む。
参照するのは Period 表（``pitch``）と ``ChannelPlan`` の型のみ。

``VERIFIERS`` は出力フォーマット名→検査関数の表（``writer.WRITERS`` と対）。
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Callable, Optional

from ..errors import ModGenError
from .pitch import NOTE_MAX, PERIODS

HEADER_SIZE = 1084
PATTERN_BYTES = 1024
ROWS = 64
CHANNELS = 4
LEFT_CHANNELS = (0, 3)     # Amiga: 1,4 = 左
RIGHT_CHANNELS = (1, 2)    # Amiga: 2,3 = 右
VOLUME_SUM_LIMIT = 120     # V15
_MAX_LOCATIONS = 3         # 1 コードあたり報告する位置の数

_PERIOD_TO_INDEX = {p: i for i, p in enumerate(PERIODS)}


class ParseError(ModGenError):
    """バイト列が .mod として解釈できない（ヘッダ未満など）。"""


@dataclass(frozen=True)
class Issue:
    level: str        # "ERROR" | "WARN" | "INFO"
    code: str         # "V01" ...
    message: str


@dataclass
class ParsedSample:
    name: bytes
    length_words: int
    finetune: int
    volume: int
    loop_start: int
    loop_length: int
    data: bytes = b""


@dataclass(frozen=True)
class ParsedCell:
    period: int
    sample: int
    effect: int
    param: int


@dataclass
class ParsedMod:
    title: bytes
    samples: list[ParsedSample]
    song_length: int
    restart: int
    order: list[int]                       # 128 エントリ
    magic: bytes
    patterns: list[list[list[ParsedCell]]] = field(default_factory=list)   # [pattern][row][ch]
    size: int = 0

    @property
    def pattern_count(self) -> int:
        """order テーブル全体の最大値 + 1（ProTracker の規約）。"""
        return max(self.order) + 1


def parse_mod(data: bytes) -> ParsedMod:
    """``M.K.`` 形式のバイト列を読む。ヘッダ（1084 byte）未満は ParseError。

    パターン・サンプルデータが不足していても、読めた分だけを返す（不足は ``verify`` の V01 が報告）。
    """
    if len(data) < HEADER_SIZE:
        raise ParseError(f"file too short: {len(data)} bytes (< {HEADER_SIZE})")
    title = data[0:20]
    samples: list[ParsedSample] = []
    for i in range(31):
        off = 20 + 30 * i
        name = data[off:off + 22]
        length, finetune, volume, loop_start, loop_len = struct.unpack(">HBBHH", data[off + 22:off + 30])
        samples.append(ParsedSample(name, length, finetune, volume, loop_start, loop_len))
    song_length, restart = data[950], data[951]
    order = list(data[952:1080])
    magic = data[1080:1084]
    pm = ParsedMod(title, samples, song_length, restart, order, magic, size=len(data))

    pos = HEADER_SIZE
    for _ in range(pm.pattern_count):
        if pos + PATTERN_BYTES > len(data):
            break
        rows = []
        for r in range(ROWS):
            row = []
            for c in range(CHANNELS):
                b0, b1, b2, b3 = data[pos:pos + 4]
                pos += 4
                row.append(ParsedCell(((b0 & 0x0F) << 8) | b1, (b0 & 0xF0) | (b2 >> 4), b2 & 0x0F, b3))
            rows.append(row)
        pm.patterns.append(rows)
    pos = HEADER_SIZE + PATTERN_BYTES * pm.pattern_count
    for s in samples:
        n = s.length_words * 2
        s.data = data[pos:pos + n] if pos <= len(data) else b""
        pos += n
    return pm


class _Report:
    """コードごとに違反を集約し、先頭数件の位置だけをメッセージに含める。"""

    def __init__(self) -> None:
        self._items: dict[str, tuple[str, list[str]]] = {}
        self._order: list[str] = []

    def add(self, level: str, code: str, where: str) -> None:
        if code not in self._items:
            self._items[code] = (level, [])
            self._order.append(code)
        self._items[code][1].append(where)

    def issues(self, descriptions: dict[str, str]) -> list[Issue]:
        out = []
        for code in self._order:
            level, locs = self._items[code]
            shown = "; ".join(locs[:_MAX_LOCATIONS])
            more = "" if len(locs) <= _MAX_LOCATIONS else f" (+{len(locs) - _MAX_LOCATIONS} more)"
            out.append(Issue(level, code, f"{descriptions[code]} [{len(locs)}件] {shown}{more}"))
        return out


_DESCRIPTIONS = {
    "V01": "ファイルサイズが規格と不一致",
    "V02": "マジックまたはタイトルが不正",
    "V03": "曲長・restart・order が不正",
    "V04": "サンプルヘッダが不正",
    "V05": "Period が Period 表にない",
    "V06": "未定義のサンプル番号を参照",
    "V07": "note を持つセルにサンプル番号がない",
    "V08": "エフェクト param が不正（0xC>64 または 0xF=0）",
    "V09": "チャンネルに許可されていないサンプル",
    "V10": "order[0] の pattern にテンポ設定（Fxx, param≥32）がない",
    "V11": "ループ境界の段差が大きい（クリックの恐れ）",
    "V12": "pattern 数が 64 を超える",
    "V13": "未使用のサンプルがある",
    "V14": "note を持たない無効果セルにサンプル番号がある",
    "V15": "左右いずれかの同時合計音量が上限を超える",
    "V16": "アルペジオが Period 表の上限を超える",
}


def _signed(b: int) -> int:
    return b - 256 if b > 127 else b


def _loop_boundary_step(data: bytes) -> Optional[tuple[float, float]]:
    """ループ境界の「段差 vs 許容量」を計算する（MOD/XM 共通のクリック検出ヒューリスティック）。
    データが空なら ``None``（呼出し側は判定をスキップする）。"""
    if not data:
        return None
    d = [_signed(b) for b in data]
    max_diff = max((abs(d[i + 1] - d[i]) for i in range(len(d) - 1)), default=0)
    step = abs(d[0] - d[-1])
    return step, max(2.0, 1.5 * max_diff)


def _check_header(pm: ParsedMod, rep: _Report) -> None:
    if pm.magic != b"M.K.":
        rep.add("ERROR", "V02", f"magic={pm.magic!r}")
    if any(not (b == 0 or 0x20 <= b <= 0x7E) for b in pm.title):
        rep.add("ERROR", "V02", "title に非 ASCII/制御文字")
    if not 1 <= pm.song_length <= 128:
        rep.add("ERROR", "V03", f"song_length={pm.song_length}")
    if pm.restart != 0x7F:
        rep.add("ERROR", "V03", f"restart=0x{pm.restart:02X}")
    for i, p in enumerate(pm.order[:pm.song_length]):
        if p >= pm.pattern_count or p >= len(pm.patterns):
            rep.add("ERROR", "V03", f"order[{i}]={p} は実 pattern 数 {len(pm.patterns)} 以上")
    if pm.pattern_count > 64:
        rep.add("ERROR", "V12", f"pattern 数={pm.pattern_count}")
    expected = HEADER_SIZE + PATTERN_BYTES * pm.pattern_count + sum(s.length_words * 2 for s in pm.samples)
    if pm.size != expected:
        rep.add("ERROR", "V01", f"size={pm.size} expected={expected}")


def _check_samples(pm: ParsedMod, rep: _Report) -> None:
    for i, s in enumerate(pm.samples, start=1):
        if s.length_words == 0:
            continue
        if s.volume > 64:
            rep.add("ERROR", "V04", f"sample {i}: volume={s.volume}")
        if s.loop_length > 1 and s.loop_start + s.loop_length > s.length_words:
            rep.add("ERROR", "V04", f"sample {i}: loop {s.loop_start}+{s.loop_length} > {s.length_words}")
        if s.loop_length > 1:
            _check_loop_boundary(i, s, rep)


def _check_loop_boundary(idx: int, s: ParsedSample, rep: _Report) -> None:
    lo, hi = s.loop_start * 2, (s.loop_start + s.loop_length) * 2
    if hi > len(s.data):
        return
    result = _loop_boundary_step(s.data[lo:hi])
    if result is None:
        return
    step, limit = result
    if step > limit:
        rep.add("WARN", "V11", f"sample {idx}: 境界段差 {step} > 許容 {limit:.1f}")


def _check_cells(pm: ParsedMod, plan, rep: _Report) -> set[int]:
    """全セルの検査。使用されたサンプル番号の集合を返す。"""
    defined = max((i for i, s in enumerate(pm.samples, start=1) if s.length_words > 0), default=0)
    used: set[int] = set()
    for p, pat in enumerate(pm.patterns):
        for r, row in enumerate(pat):
            for c, cell in enumerate(row):
                where = f"pattern {p} row {r} ch{c + 1}"
                if cell.sample:
                    used.add(cell.sample)
                    if cell.sample > defined:
                        rep.add("ERROR", "V06", f"{where}: sample {cell.sample}")
                if cell.period and cell.period not in _PERIOD_TO_INDEX:
                    rep.add("ERROR", "V05", f"{where}: period {cell.period}")
                if cell.period and cell.sample == 0:
                    rep.add("ERROR", "V07", where)
                if cell.effect == 0xC and cell.param > 64:
                    rep.add("ERROR", "V08", f"{where}: C{cell.param:02X}")
                if cell.effect == 0xF and cell.param == 0:
                    rep.add("ERROR", "V08", f"{where}: F00")
                if plan is not None and cell.sample and cell.sample not in plan[c].allowed:
                    rep.add("ERROR", "V09", f"{where}: sample {cell.sample} on {plan[c].name}")
                if not cell.period and cell.sample and cell.effect == 0 and cell.param == 0:
                    rep.add("WARN", "V14", f"{where}: sample {cell.sample}")
                if cell.effect == 0 and cell.param and cell.period in _PERIOD_TO_INDEX:
                    t = _PERIOD_TO_INDEX[cell.period]
                    top = t + max(cell.param >> 4, cell.param & 0xF)
                    if top > NOTE_MAX:
                        rep.add("ERROR", "V16", f"{where}: t={t} arp={cell.param:02X}")
    return used


def _check_tempo(pm: ParsedMod, rep: _Report) -> None:
    if not pm.order or pm.order[0] >= len(pm.patterns):
        return
    first = pm.patterns[pm.order[0]]
    if not any(c.effect == 0xF and c.param >= 32 for row in first for c in row):
        rep.add("ERROR", "V10", f"pattern {pm.order[0]}")


def _check_volume_sum(pm: ParsedMod, rep: _Report) -> None:
    """再生順に各チャンネルの音量を追跡し、左（Ch1+Ch4）・右（Ch2+Ch3）の合計を検査する。"""
    vol = [0] * CHANNELS
    seen: set[tuple[int, int]] = set()
    for pos, p in enumerate(pm.order[:pm.song_length]):
        if p >= len(pm.patterns):
            continue
        for r, row in enumerate(pm.patterns[p]):
            for c, cell in enumerate(row):
                if cell.effect == 0xC:
                    vol[c] = cell.param
                if cell.period and cell.sample and cell.effect != 0xC:
                    vol[c] = pm.samples[cell.sample - 1].volume
            left = sum(vol[c] for c in LEFT_CHANNELS)
            right = sum(vol[c] for c in RIGHT_CHANNELS)
            if (left > VOLUME_SUM_LIMIT or right > VOLUME_SUM_LIMIT) and (p, r) not in seen:
                seen.add((p, r))
                rep.add("WARN", "V15", f"pattern {p} row {r}: L={left} R={right}")


def verify(data: bytes, plan=None) -> list[Issue]:
    """構造検査。``plan``（ChannelPlan）を渡すと V09 も検査する。"""
    try:
        pm = parse_mod(data)
    except ParseError as e:
        return [Issue("ERROR", "V01", str(e))]
    rep = _Report()
    _check_header(pm, rep)
    _check_samples(pm, rep)
    used = _check_cells(pm, plan, rep)
    _check_tempo(pm, rep)
    _check_volume_sum(pm, rep)
    for i, s in enumerate(pm.samples, start=1):
        if s.length_words > 0 and i not in used:
            rep.add("INFO", "V13", f"sample {i}")
    return rep.issues(_DESCRIPTIONS)


def has_errors(issues: list[Issue]) -> bool:
    return any(i.level == "ERROR" for i in issues)


# ============================================================
# XM（FastTracker II Extended Module。EXT-6、CORE_EXTENSION_DESIGN §4.6④）
# ============================================================

XM_FIXED_HEADER = 60     # ID(17)+name(20)+0x1A(1)+tracker(20)+version(2)
XM_ORDER_TABLE_SIZE = 256


@dataclass(frozen=True)
class ParsedXMCell:
    note: int          # 0=無音、1..96=note+1（本プロジェクトは 1..36 のみ使用）
    instrument: int
    volume: int        # 本プロジェクトの writer は常に 0（vol column 不使用）
    effect: int
    param: int


@dataclass
class ParsedXMSample:
    name: bytes
    length: int         # バイト
    loop_start: int      # バイト
    loop_length: int      # バイト
    volume: int
    finetune: int
    sample_type: int
    pan: int
    relative_note: int
    data: bytes = b""


@dataclass
class ParsedXMInstrument:
    name: bytes
    n_samples: int
    samples: list[ParsedXMSample] = field(default_factory=list)


@dataclass
class ParsedXM:
    magic: bytes
    title: bytes
    song_length: int
    n_channels: int
    n_patterns: int
    n_instruments: int
    order: list[int]                                            # 256 エントリ
    patterns: list[list[list[ParsedXMCell]]] = field(default_factory=list)   # [pattern][row][ch]
    instruments: list[ParsedXMInstrument] = field(default_factory=list)
    size: int = 0
    consumed: int = 0                                            # 実際に読み進めたバイト数


def _unpack_xm_cell(data: bytes, pos: int) -> tuple[ParsedXMCell, int]:
    if pos >= len(data):
        return ParsedXMCell(0, 0, 0, 0, 0), pos
    b0 = data[pos]
    pos += 1
    if b0 & 0x80:
        flags = b0 & 0x1F
        note = instrument = volume = effect = param = 0
        if flags & 0x01:
            note, pos = data[pos], pos + 1
        if flags & 0x02:
            instrument, pos = data[pos], pos + 1
        if flags & 0x04:
            volume, pos = data[pos], pos + 1
        if flags & 0x08:
            effect, pos = data[pos], pos + 1
        if flags & 0x10:
            param, pos = data[pos], pos + 1
    else:
        note = b0
        instrument, volume, effect, param = data[pos:pos + 4]
        pos += 4
    return ParsedXMCell(note, instrument, volume, effect, param), pos


def parse_xm(data: bytes) -> ParsedXM:
    """``.xm`` 形式のバイト列を読む。固定ヘッダ（60 byte）未満は ParseError。

    ``parse_mod`` と同じ方針で、書込側（``writer.serialize_xm``）とは独立に ``struct`` で直接読む。
    パターン・インストゥルメントデータが不足していても、読めた分だけを返す。
    """
    if len(data) < XM_FIXED_HEADER + 4:
        raise ParseError(f"file too short: {len(data)} bytes (< {XM_FIXED_HEADER + 4})")
    magic = data[0:17]
    title = data[17:37]
    header_size = struct.unpack("<I", data[60:64])[0]
    hdr = data[64:64 + 16]
    if len(hdr) < 16:
        raise ParseError("XM header truncated")
    song_length, _restart, n_channels, n_patterns, n_instruments, _flags, _speed, _bpm = \
        struct.unpack("<8H", hdr)
    order = list(data[80:80 + XM_ORDER_TABLE_SIZE])
    pm = ParsedXM(magic, title, song_length, n_channels, n_patterns, n_instruments, order, size=len(data))

    # header_size は offset 60（header_size フィールド自身）を起点に数える、というのが実際の
    # FT2/XM 規約（writer.XM_HEADER_SIZE のコメント参照）。64 起点ではない。
    pos = XM_FIXED_HEADER + header_size
    for _ in range(n_patterns):
        if pos + 9 > len(data):
            break
        phdr_len, _packing, n_rows, packed_size = struct.unpack("<IBHH", data[pos:pos + 9])
        pos += max(9, phdr_len)
        packed = data[pos:pos + packed_size]
        pos += packed_size
        if packed_size == 0:
            rows = [[ParsedXMCell(0, 0, 0, 0, 0) for _ in range(n_channels)] for _ in range(n_rows)]
        else:
            rows = []
            cpos = 0
            for _r in range(n_rows):
                row = []
                for _c in range(n_channels):
                    cell, cpos = _unpack_xm_cell(packed, cpos)
                    row.append(cell)
                rows.append(row)
        pm.patterns.append(rows)

    for _ in range(n_instruments):
        if pos + 4 > len(data):
            break
        inst_size = struct.unpack("<I", data[pos:pos + 4])[0]
        inst_start = pos
        name = data[pos + 4:pos + 26]
        n_samples = struct.unpack("<H", data[pos + 27:pos + 29])[0] if pos + 29 <= len(data) else 0
        sample_header_size = 40
        if n_samples > 0 and pos + 33 <= len(data):
            sample_header_size = struct.unpack("<I", data[pos + 29:pos + 33])[0]
        pos = inst_start + max(inst_size, 29)
        samples: list[ParsedXMSample] = []
        for _s in range(n_samples):
            sh = data[pos:pos + sample_header_size]
            pos += sample_header_size
            if len(sh) < 18:
                break
            length, loop_start, loop_len, volume, finetune, stype, pan, relnote, _resv = \
                struct.unpack("<IIIBbBBbB", sh[:18])
            sname = sh[18:40]
            samples.append(ParsedXMSample(sname, length, loop_start, loop_len, volume, finetune,
                                           stype, pan, relnote))
        for s in samples:
            s.data = data[pos:pos + s.length] if pos <= len(data) else b""
            pos += s.length
        pm.instruments.append(ParsedXMInstrument(name, n_samples, samples))

    pm.consumed = pos
    return pm


_XM_DESCRIPTIONS = {
    "V01": "ファイルサイズが宣言内容と不一致",
    "V02": "マジックが不正",
    "V03": "曲長・order が不正",
    "V04": "サンプルヘッダが不正",
    "V06": "未定義のインストゥルメント番号を参照",
    "V07": "note を持つセルにインストゥルメント番号がない",
    "V08": "エフェクト param が不正（0xC>64 または 0xF=0）",
    "V09": "チャンネルに許可されていないインストゥルメント",
    "V10": "order[0] の pattern にテンポ設定（Fxx, param≥32）がない",
    "V11": "ループ境界の段差が大きい（クリックの恐れ）",
    "V12": "pattern 数が 64 を超える",
    "V13": "未使用のインストゥルメントがある",
    "V14": "note を持たない無効果セルにインストゥルメント番号がある",
    "V15": "パン加重した左右合計音量が上限を超える",
    "V16": "アルペジオが note 上限を超える",
}


def _check_xm_header(pm: ParsedXM, rep: _Report) -> None:
    if pm.magic != b"Extended Module: ":
        rep.add("ERROR", "V02", f"magic={pm.magic!r}")
    if not 1 <= pm.song_length <= len(pm.order):
        rep.add("ERROR", "V03", f"song_length={pm.song_length}")
    for i, p in enumerate(pm.order[:pm.song_length]):
        if p >= len(pm.patterns):
            rep.add("ERROR", "V03", f"order[{i}]={p} は実 pattern 数 {len(pm.patterns)} 以上")
    if pm.n_patterns > 64:
        rep.add("ERROR", "V12", f"pattern 数={pm.n_patterns}")
    if pm.size != pm.consumed:
        rep.add("ERROR", "V01", f"size={pm.size} consumed={pm.consumed}")


def _check_xm_samples(pm: ParsedXM, rep: _Report) -> None:
    for i, inst in enumerate(pm.instruments, start=1):
        for s in inst.samples:
            if s.length == 0:
                continue
            if s.volume > 64:
                rep.add("ERROR", "V04", f"instrument {i}: volume={s.volume}")
            if (s.sample_type & 0x03) and s.loop_start + s.loop_length > s.length:
                rep.add("ERROR", "V04", f"instrument {i}: loop {s.loop_start}+{s.loop_length} > {s.length}")
            if (s.sample_type & 0x03) and s.loop_length > 2:
                _check_xm_loop_boundary(i, s, rep)


def _check_xm_loop_boundary(idx: int, s: ParsedXMSample, rep: _Report) -> None:
    lo, hi = s.loop_start, s.loop_start + s.loop_length
    if hi > len(s.data):
        return
    result = _loop_boundary_step(s.data[lo:hi])
    if result is None:
        return
    step, limit = result
    if step > limit:
        rep.add("WARN", "V11", f"instrument {idx}: 境界段差 {step} > 許容 {limit:.1f}")


def _check_xm_cells(pm: ParsedXM, plan, rep: _Report) -> set[int]:
    defined = len(pm.instruments)
    used: set[int] = set()
    for p, pat in enumerate(pm.patterns):
        for r, row in enumerate(pat):
            for c, cell in enumerate(row):
                where = f"pattern {p} row {r} ch{c + 1}"
                if cell.instrument:
                    used.add(cell.instrument)
                    if cell.instrument > defined:
                        rep.add("ERROR", "V06", f"{where}: instrument {cell.instrument}")
                if cell.note and cell.instrument == 0:
                    rep.add("ERROR", "V07", where)
                if cell.effect == 0xC and cell.param > 64:
                    rep.add("ERROR", "V08", f"{where}: C{cell.param:02X}")
                if cell.effect == 0xF and cell.param == 0:
                    rep.add("ERROR", "V08", f"{where}: F00")
                if plan is not None and cell.instrument and cell.instrument not in plan[c].allowed:
                    rep.add("ERROR", "V09", f"{where}: instrument {cell.instrument} on {plan[c].name}")
                if not cell.note and cell.instrument and cell.effect == 0 and cell.param == 0:
                    rep.add("WARN", "V14", f"{where}: instrument {cell.instrument}")
                if cell.effect == 0 and cell.param and cell.note:
                    t = cell.note - 1
                    top = t + max(cell.param >> 4, cell.param & 0xF)
                    if top > NOTE_MAX:
                        rep.add("ERROR", "V16", f"{where}: t={t} arp={cell.param:02X}")
    return used


def _check_xm_tempo(pm: ParsedXM, rep: _Report) -> None:
    if not pm.order or pm.order[0] >= len(pm.patterns):
        return
    first = pm.patterns[pm.order[0]]
    if not any(c.effect == 0xF and c.param >= 32 for row in first for c in row):
        rep.add("ERROR", "V10", f"pattern {pm.order[0]}")


def _check_xm_volume_sum(pm: ParsedXM, rep: _Report) -> None:
    """再生順に各チャンネルの音量を追跡し、instrument.pan で加重した左右合計を検査する
    （MOD の固定 L/R チャンネル割当の一般化。CORE_EXTENSION_DESIGN §4.6④）。"""
    n = pm.n_channels
    vol = [0] * n
    pan = [128] * n
    seen: set[tuple[int, int]] = set()
    for p in pm.order[:pm.song_length]:
        if p >= len(pm.patterns):
            continue
        for r, row in enumerate(pm.patterns[p]):
            for c, cell in enumerate(row):
                if cell.effect == 0xC:
                    vol[c] = cell.param
                if cell.note and cell.instrument and cell.effect != 0xC:
                    inst = pm.instruments[cell.instrument - 1] if cell.instrument <= len(pm.instruments) else None
                    if inst and inst.samples:
                        vol[c] = inst.samples[0].volume
                        pan[c] = inst.samples[0].pan
            left = sum(vol[c] * (255 - pan[c]) / 255.0 for c in range(n))
            right = sum(vol[c] * pan[c] / 255.0 for c in range(n))
            if (left > VOLUME_SUM_LIMIT or right > VOLUME_SUM_LIMIT) and (p, r) not in seen:
                seen.add((p, r))
                rep.add("WARN", "V15", f"pattern {p} row {r}: L={left:.0f} R={right:.0f}")


def verify_xm(data: bytes, plan=None) -> list[Issue]:
    """XM の構造検査。``plan``（ChannelPlan）を渡すと V09 も検査する。"""
    try:
        pm = parse_xm(data)
    except ParseError as e:
        return [Issue("ERROR", "V01", str(e))]
    rep = _Report()
    _check_xm_header(pm, rep)
    _check_xm_samples(pm, rep)
    used = _check_xm_cells(pm, plan, rep)
    _check_xm_tempo(pm, rep)
    _check_xm_volume_sum(pm, rep)
    for i, inst in enumerate(pm.instruments, start=1):
        if inst.samples and inst.samples[0].length > 0 and i not in used:
            rep.add("INFO", "V13", f"instrument {i}")
    return rep.issues(_XM_DESCRIPTIONS)


# 出力フォーマット名 → 検査関数
VERIFIERS: dict[str, Callable[..., list[Issue]]] = {"mod": verify, "xm": verify_xm}
