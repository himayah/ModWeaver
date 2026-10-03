"""データモデル（DESIGN.md §3）。

- ``GmVoice``: 楽器 1 つの GM 音色（ジャンルの宣言が使う。形式系ではないのでここ）。
- ``Cell`` / ``Pattern``: MOD の 1 セルと、行×チャンネルの領域（MOD の writer が読む。Realizer は ``core/native.py`` の
  ``RealizedSong`` を作り、MOD だけ ``native.to_mod_song`` でこの表現に直して ``core/writer.py`` に渡す）。
- ``SampleSpec`` / ``Song``: サンプルと、MOD の曲。
- ``ChordSpec`` / ``ChordDef``: 和音の記述と、調・音域を適用して具体化したもの（``core/harmony.py`` の ``voice()``）。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from ..errors import CellConflictError, PitchRangeError, SampleConstraintError
from .pitch import NOTE_MAX, NOTE_MIN, PERIODS

log = logging.getLogger("mod_weaver")

MAX_SAMPLES = 31
MAX_SAMPLE_BYTES = 131070  # 65535 words


# ============================================================
# GmVoice
# ============================================================
# 形式系（writer・native*・render・verify）ではなくここに置く理由: genres/*.py が core の形式系を import しない
# （DESIGN.md §2.1・§10.1 I8）。Instrument.gm の型として genres が GmVoice を参照する必要があるので、
# 形式系ではないここに置く。

@dataclass(frozen=True)
class GmVoice:
    """楽器 1 つの GM 音色。``program``（0..127、旋律楽器）か ``drum_note``（35..81、ch10）のどちらか一方。"""
    program: Optional[int] = None
    drum_note: Optional[int] = None

    def __post_init__(self) -> None:
        if (self.program is None) == (self.drum_note is None):
            raise ValueError("GmVoice needs exactly one of program / drum_note")
        if self.program is not None and not 0 <= self.program <= 127:
            raise ValueError(f"GM program out of range: {self.program}")
        if self.drum_note is not None and not 27 <= self.drum_note <= 87:
            raise ValueError(f"GM drum note out of range: {self.drum_note}")

    @property
    def is_drum(self) -> bool:
        return self.drum_note is not None


# ============================================================
# Cell
# ============================================================

@dataclass(frozen=True)
class Cell:
    note: Optional[int] = None     # tracker note index or None(休)
    sample: int = 0                # 0=指定なし, 1..31
    effect: int = 0                # 0..0xF
    param: int = 0                 # 0..0xFF
    vol: Optional[int] = None      # 0..64。effect/param と排他

    def __post_init__(self) -> None:
        if self.note is not None and not NOTE_MIN <= self.note <= NOTE_MAX:
            raise PitchRangeError(f"note index out of range: {self.note}")
        if not 0 <= self.sample <= MAX_SAMPLES:
            raise CellConflictError(f"sample out of range: {self.sample}")
        if not 0 <= self.effect <= 0xF:
            raise CellConflictError(f"effect out of range: {self.effect}")
        if not 0 <= self.param <= 0xFF:
            raise CellConflictError(f"param out of range: {self.param}")
        if self.vol is not None:
            if not 0 <= self.vol <= 64:
                raise CellConflictError(f"vol out of range: {self.vol}")
            if self.effect != 0 or self.param != 0:
                raise CellConflictError(
                    f"vol and effect cannot share a cell (vol={self.vol}, "
                    f"effect={self.effect:X}, param={self.param:02X})"
                )

    @property
    def has_effect(self) -> bool:
        """アルペジオ（0xy）も「効果あり」とみなす。"""
        return self.effect != 0 or self.param != 0

    @property
    def is_empty(self) -> bool:
        return (
            self.note is None
            and self.sample == 0
            and self.vol is None
            and not self.has_effect
        )

    def serialize(self) -> bytes:
        """ProTracker 4 byte セル。``vol`` は ``0xC vv`` に変換される。"""
        period = 0 if self.note is None else PERIODS[self.note]
        effect, param = (0xC, self.vol) if self.vol is not None else (self.effect, self.param)
        b0 = (((self.sample >> 4) & 0x0F) << 4) | ((period >> 8) & 0x0F)
        b1 = period & 0xFF
        b2 = ((self.sample & 0x0F) << 4) | (effect & 0x0F)
        return bytes([b0, b1, b2, param & 0xFF])


EMPTY_CELL = Cell()


# ============================================================
# Pattern
# ============================================================

class Pattern:
    """行×チャンネルのセルの領域（MOD の 1 pattern。既定 64 row × 4 ch）。"""

    def __init__(self, rows: int = 64, channels: int = 4) -> None:
        if rows < 1 or channels < 1:
            raise ValueError(f"pattern needs positive rows and channels: {rows}x{channels}")
        self.rows = rows
        self.channels = channels
        self._cells: list[list[Cell]] = [[EMPTY_CELL] * channels for _ in range(rows)]

    def put(self, row: int, ch: int, cell: Cell) -> None:
        if not (0 <= row < self.rows and 0 <= ch < self.channels):
            raise IndexError(f"cell position out of range: row={row} ch={ch} ({self.rows}x{self.channels})")
        self._cells[row][ch] = cell

    def get(self, row: int, ch: int) -> Cell:
        return self._cells[row][ch]

    def serialize(self) -> bytes:
        return b"".join(c.serialize() for r in self._cells for c in r)


# ============================================================
# SampleSpec / Song
# ============================================================

@dataclass
class SampleSpec:
    name: str                      # ASCII ≤22
    data: bytes                    # 偶数長 ≥2、符号なし表現の 8bit（``bits=8``）または 16bit signed PCM
    volume: int                    # 0..64
    loop: Optional[tuple[int, int]] = None   # (start_words, length_words) length>1。None は (0,1)。
    # ↑ "word" は常に「data の2 byte」を指す（8-bit なら 2 サンプル、16-bit なら 1 サンプル）。
    #   writer 側は常に ×2 するだけで byte 位置に戻せる（DESIGN.md §4.8）
    rate_note: int = 24            # 生成レートを決める tracker note（既定 C-3）
    shift: int = 0                 # n = t + shift（DESIGN.md §3.1）
    pitched: bool = True           # False: 常に rate_note で発音（打楽器）
    finetune: int = 0
    pan: int = 128                 # EXT-6: 0=左、128=中央、255=右。MOD の serialize() は参照しない
    sounding_hz: Optional[float] = None
    # ↑ tracker note ``rate_note``（finetune 0）で鳴らしたときに実際に聞こえる基本周波数（Hz）。
    #   synth.render() が記録する。音高を持たない音色は None。MIDI 出力が実音の高さを求めるのに使う
    #   （合成は dsp.sample_rate()＝実際の Paula 再生レートの半分を基準に波形を作るため、論理 note の
    #   pitch.hz(n) とは一致しない。DESIGN.md §3.1）。oversample（m）に依存しない値（DESIGN.md §3.1）
    bits: int = 8                  # 8 | 16（DESIGN.md §4.8）。8-bit の全ジャンルは既定のまま
    rate_hz: Optional[float] = None
    # ↑ ``rate_note`` で鳴らすときに実際に使うべき再生レート（Hz）。synth.render() が oversample から
    #   計算する。S3M/IT の C2Spd・C5Speed や XM の relative_note+finetune は、この値から求める
    #   （DESIGN.md §4.8・§7）。MOD は Period 表だけで再生レートが決まるので参照しない

    @property
    def length_words(self) -> int:
        return len(self.data) // 2

    @property
    def loop_header(self) -> tuple[int, int]:
        """ヘッダに書く (loop_start, loop_length)（words）。"""
        return self.loop if self.loop is not None else (0, 1)

    def validate(self) -> None:
        """サンプル制約を検査する。違反は SampleConstraintError。"""
        n = self.name
        if len(n) > 22 or not n.isascii():
            raise SampleConstraintError(f"sample name must be ASCII and <=22 chars: {n!r}")
        if self.bits not in (8, 16):
            raise SampleConstraintError(f"sample {n!r}: bits must be 8 or 16: {self.bits}")
        if len(self.data) < 2 or len(self.data) % 2 != 0:
            raise SampleConstraintError(f"sample {n!r}: length must be even and >=2 (got {len(self.data)})")
        if self.bits == 8 and len(self.data) > MAX_SAMPLE_BYTES:
            # MOD/S3M の 8-bit サイズ上限（65535 word）。16-bit や他形式の上限は Realizer/SampleCaps が
            # 持つ（DESIGN.md §3.2・§4.8）ので、ここでは 8-bit のときだけ検査する
            raise SampleConstraintError(f"sample {n!r}: length {len(self.data)} exceeds {MAX_SAMPLE_BYTES}")
        if not 0 <= self.volume <= 64:
            raise SampleConstraintError(f"sample {n!r}: volume out of range: {self.volume}")
        if not NOTE_MIN <= self.rate_note <= NOTE_MAX:
            raise SampleConstraintError(f"sample {n!r}: rate_note out of range: {self.rate_note}")
        if not -8 <= self.finetune <= 7:
            raise SampleConstraintError(f"sample {n!r}: finetune out of range: {self.finetune}")
        if not 0 <= self.pan <= 255:
            raise SampleConstraintError(f"sample {n!r}: pan out of range: {self.pan}")
        if self.loop is not None:
            start, length = self.loop
            if start < 0 or length <= 1 or start + length > self.length_words:
                raise SampleConstraintError(
                    f"sample {n!r}: loop {self.loop} out of range (length={self.length_words} words)"
                )


@dataclass
class Song:
    title: str                     # ASCII ≤20
    samples: list[SampleSpec]      # 位置=sample番号-1
    patterns: list[Pattern]
    order: list[int]               # 1..128 エントリ
    instrument_names: tuple[str, ...] = ()   # 楽器名（sample 番号順）


@dataclass(frozen=True)
class ChordSpec:                   # 調非依存の和音記述（度数ではなく半音オフセット）
    root: int                      # 主音からの半音 0..11
    quality: str                   # CHORD_QUALITIES のキー
    bass: Optional[int] = None     # スラッシュ／ペダル用（主音からの半音）。None=root
    label: str = ""


@dataclass(frozen=True)
class ChordDef:                    # 具体化済み（調・音域適用後）
    label: str
    bass: int                      # ベース logical note
    harmony: int                   # パッド/持続用の代表音
    chord_tones: tuple[int, ...]   # 強拍用（メロディ音域）
    scale_tones: tuple[int, ...]   # 経過音用
    arp: Optional[int] = None      # 0xy の param（新ジャンルのみ）
    explicit: bool = False         # True: 手書きボイシング（Nostalgic）
