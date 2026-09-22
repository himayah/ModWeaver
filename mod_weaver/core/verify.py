"""独立パーサ ``parse_mod`` と構造検査 ``verify``（設計書 §6.4）。

書込側（``writer`` / ``model``）とは独立に、バイト列を ``struct`` で直接読む。
参照するのは Period 表（``pitch``）と ``ChannelPlan`` の型のみ。

``VERIFIERS`` は出力フォーマット名→検査関数の表（``writer.WRITERS`` と対）。
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Callable

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
    d = [_signed(b) for b in s.data[lo:hi]]
    max_diff = max((abs(d[i + 1] - d[i]) for i in range(len(d) - 1)), default=0)
    step = abs(d[0] - d[-1])
    if step > max(2.0, 1.5 * max_diff):
        rep.add("WARN", "V11", f"sample {idx}: 境界段差 {step} > 許容 {max(2.0, 1.5 * max_diff):.1f}")


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


# 出力フォーマット名 → 検査関数
VERIFIERS: dict[str, Callable[..., list[Issue]]] = {"mod": verify}
