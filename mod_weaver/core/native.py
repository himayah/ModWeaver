"""トラッカー形式（MOD・S3M・XM・IT）共通の中間表現（FRAMEWORK_REDESIGN.md §9.6・§10）。

``framework/realize/tracker.py`` が Score からこの形を作り、形式ごとの writer（``native_s3m``・
``native_xm``・``native_it``、MOD は ``to_mod_song``）が**換算なしで**書き出す（§10 冒頭）。
旧来の ``model.Cell``（MOD 風のエフェクト表現）とは別物で、F8 までは新旧が並行する。

- ``RCell.note``: **0 始まりの半音番号**（C-0 = 0）。S3M は C-4 = 48、XM は C-4 = 48（書くとき +1）、
  IT は C-5 = 60 が ``rate_hz`` で鳴る基準。MOD だけは tracker note t（0..35、``model.Cell`` と同じ）。
  特別な値 ``NOTE_CUT``（即時に止める）・``NOTE_OFF``（キーオフ）。
- ``RCell.fx``: ``(コマンド, param)``。コマンドは**その形式の表記**の1文字（MOD は ``"4"``・``"E"``、S3M・IT は
  ``"H"``・``"S"``、XM は ``"4"``・``"E"``）。
- ``RCell.vol``: 0..64。MOD は発音の ``Cxx``（``fx`` と排他）、他形式はボリューム列。
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Callable, Optional

from ..errors import CellConflictError, ChannelConflictError
from .model import SampleSpec

NOTE_CUT = -1     # 即時に止める（S3M・IT は ^^^、XM はボリューム列 0、MOD は Cxx 00 に変換済みで使わない）
NOTE_OFF = -2     # キーオフ（XM は 97、IT は ===。エンベロープのリリースを始める）

Fx = tuple[str, int]


@dataclass(frozen=True)
class RCell:
    note: Optional[int] = None
    sample: int = 0
    vol: Optional[int] = None
    fx: Optional[Fx] = None

    def __post_init__(self) -> None:
        if self.vol is not None and not 0 <= self.vol <= 64:
            raise CellConflictError(f"vol out of range: {self.vol}")
        if self.fx is not None and not 0 <= self.fx[1] <= 0xFF:
            raise CellConflictError(f"param out of range: {self.fx}")

    @property
    def is_empty(self) -> bool:
        return self.note is None and not self.sample and self.vol is None and self.fx is None


EMPTY = RCell()


class RGrid:
    """行×チャンネルのセル領域（区間の作業領域にも pattern にも使う）。

    ``exclusive``: ``vol`` と ``fx`` を同じセルに置けない形式（MOD）。``try_insert_command`` の探索が変わる。
    """

    def __init__(self, rows: int, channels: int, *, exclusive: bool = False) -> None:
        if rows <= 0:
            raise ValueError(f"rows must be positive: {rows}")
        self.rows = rows
        self.channels = channels
        self.exclusive = exclusive
        self._cells: list[list[RCell]] = [[EMPTY] * channels for _ in range(rows)]

    def _check(self, row: int, ch: int) -> None:
        if not 0 <= row < self.rows:
            raise ChannelConflictError(f"row out of range: {row} (rows={self.rows})")
        if not 0 <= ch < self.channels:
            raise ChannelConflictError(f"channel out of range: {ch}")

    def get(self, row: int, ch: int) -> RCell:
        self._check(row, ch)
        return self._cells[row][ch]

    def put(self, row: int, ch: int, cell: RCell) -> None:
        self._check(row, ch)
        if self.exclusive and cell.vol is not None and cell.fx is not None:
            raise CellConflictError(f"vol and fx cannot share a cell here: {cell}")
        self._cells[row][ch] = cell

    replace = put

    def try_insert_command(self, row: int, fx: Fx, prefer: Optional[int] = None) -> bool:
        """row の空きチャンネルへ ``fx`` を書く。探索順: ``prefer``（制御チャンネル）の空き → 空のセル →
        音量・エフェクトの無い発音のセル（そのセルの音は残る）。無ければ False（DESIGN.md §3.2 を一般化）。"""
        if prefer is not None and self.get(row, prefer).is_empty:
            self.put(row, prefer, RCell(fx=fx))
            return True
        for ch in range(self.channels):
            if self.get(row, ch).is_empty:
                self.put(row, ch, RCell(fx=fx))
                return True
        for ch in range(self.channels):
            c = self.get(row, ch)
            if c.fx is None and (c.note is not None or c.sample) and (c.vol is None or not self.exclusive):
                self.put(row, ch, RCell(c.note, c.sample, c.vol, fx))
                return True
        return False

    def mapped(self, fn: Callable[[RCell], RCell]) -> "RGrid":
        new = copy.copy(self)
        new._cells = [[fn(c) for c in row] for row in self._cells]
        return new


@dataclass
class RealizedSong:
    """Realizer の出力（§10）。writer はこれだけを読む。"""
    format: str                                   # "mod" | "s3m" | "xm" | "it"
    title: str
    samples: list[SampleSpec]                     # sample 番号順。``rate_hz`` は基準ノートで鳴らすときのレート
    patterns: list[RGrid]
    order: list[int]
    channel_pans: tuple[int, ...]                 # 0..255。MOD は参照しない（プレイヤー固定）、XM は samples[].pan を使う
    initial_bpm: int
    initial_speed: int = 6
    mix_volume: int = 48                          # S3M マスター音量・IT mix volume
    instrument_names: tuple[str, ...] = ()
    sample_release: tuple[Optional[float], ...] = ()   # sample 番号順の ``Instrument.release_s``（None は即時に止める）
    measure_rows: tuple[tuple[int, ...], ...] = ()     # pattern ごとの小節長の列（MIDI 用の情報。MOD の WriteOptions へ）
    rows_per_measure: int = 16

    @property
    def n_channels(self) -> int:
        return self.patterns[0].channels if self.patterns else 0

    def release_of(self, sample_no: int) -> Optional[float]:
        return self.sample_release[sample_no - 1] if 0 < sample_no <= len(self.sample_release) else None


# ============================================================
# MOD への変換（writer は既存の core/writer.serialize をそのまま使う）
# ============================================================

def to_mod_song(rs: RealizedSong):
    from .model import Cell, Pattern, Song

    pats = []
    for g in rs.patterns:
        pat = Pattern(rows=g.rows, channels=g.channels)
        for r in range(g.rows):
            for ch in range(g.channels):
                c = g.get(r, ch)
                if c.is_empty:
                    continue
                effect, param = (int(c.fx[0], 16), c.fx[1]) if c.fx is not None else (0, 0)
                note = c.note if c.note is not None and c.note >= 0 else None
                pat.put(r, ch, Cell(note, c.sample, effect, param, c.vol))
        pats.append(pat)
    return Song(title=rs.title, samples=rs.samples, patterns=pats, order=rs.order,
                instrument_names=rs.instrument_names)


# ============================================================
# 形式ごとの入口（writer・検査器へ振り分ける）
# ============================================================

def serialize(rs: RealizedSong) -> bytes:
    """``RealizedSong`` を形式のバイト列にする（MP3 は IT の ``RealizedSong`` を ``render.render_mp3_from_it`` へ）。"""
    from . import native_it, native_s3m, native_xm, writer

    if rs.format == "mod":
        return writer.serialize(to_mod_song(rs))
    try:
        mod = {"s3m": native_s3m, "xm": native_xm, "it": native_it}[rs.format]
    except KeyError:
        raise ValueError(f"unknown tracker format {rs.format!r}") from None
    return mod.serialize(rs)


def verify(fmt: str, data: bytes) -> list:
    """形式の検査器（``verify.Issue`` の列）。"""
    from . import native_it, native_s3m, native_xm, verify as verify_mod

    if fmt == "mod":
        return verify_mod.verify(data)
    if fmt == "midi":
        from . import native_midi
        return native_midi.verify(data)
    return {"s3m": native_s3m, "xm": native_xm, "it": native_it}[fmt].verify(data)
