"""ProTracker ``M.K.`` および FastTracker II ``.xm`` シリアライザと原子的書込
（設計書 §6.3、CORE_EXTENSION_DESIGN §4.6③ EXT-6）。

``WRITERS`` は出力フォーマット名→シリアライザの表（``"mod"``／``"xm"``）。
"""
from __future__ import annotations

import os
import struct
from pathlib import Path
from typing import Callable, Union

from ..errors import OutputError, PlanError
from .model import Cell, Pattern, SampleSpec, Song

HEADER_SAMPLES = 31
ORDER_TABLE_SIZE = 128
TITLE_SIZE = 20
MAGIC = b"M.K."

XM_MAX_CHANNELS = 32   # target_format != "mod" のプロファイルが宣言できる channel_plan の上限


def _ascii_bytes(text: str, limit: int, what: str) -> bytes:
    if len(text) > limit or not text.isascii():
        raise PlanError(f"{what} must be ASCII and <= {limit} chars: {text!r}")
    return text.encode("ascii")


def serialize(song: Song) -> bytes:
    """Song を ``M.K.`` 形式のバイト列へ変換する。"""
    if not 1 <= len(song.order) <= ORDER_TABLE_SIZE:
        raise PlanError(f"order length must be 1..{ORDER_TABLE_SIZE}: {len(song.order)}")
    if len(song.samples) > HEADER_SAMPLES:
        raise PlanError(f"too many samples: {len(song.samples)} > {HEADER_SAMPLES}")
    if min(song.order) < 0:
        raise PlanError(f"negative pattern number in order: {song.order}")
    n_patterns = max(song.order) + 1
    if n_patterns > len(song.patterns):
        raise PlanError(
            f"order refers to pattern {n_patterns - 1} but only {len(song.patterns)} patterns exist"
        )

    out = bytearray()
    out += _ascii_bytes(song.title, TITLE_SIZE, "title").ljust(TITLE_SIZE, b"\x00")

    for i in range(HEADER_SAMPLES):
        if i < len(song.samples):
            s = song.samples[i]
            s.validate()
            out += _ascii_bytes(s.name, 22, "sample name").ljust(22, b"\x00")
            out += struct.pack(">H", s.length_words)
            out += bytes([s.finetune & 0x0F])
            out += bytes([s.volume & 0xFF])
            out += struct.pack(">HH", *s.loop_header)
        else:
            out += b"\x00" * 30

    out += struct.pack(">BB", len(song.order), 0x7F)
    out += bytes(song.order + [0] * (ORDER_TABLE_SIZE - len(song.order)))
    out += MAGIC

    for pat in song.patterns[:n_patterns]:
        out += pat.serialize()
    for s in song.samples:
        out += s.data
    return bytes(out)


# ============================================================
# XM（FastTracker II Extended Module。EXT-6）
# ============================================================
#
# CORE_EXTENSION_DESIGN §4.6③ のスコープどおり、エンベロープ／複数サンプルキーマップ／XM 独自の
# vol column は使わない（1 Instrument = 1 sample、Cell の vol/effect 排他制約をそのまま流用）。
#
# §11 の要検証事項: 本実装はバイナリレイアウトの公開仕様の記憶に基づく机上実装であり、実機・
# 実プレイヤー（OpenMPT/libxmp/MilkyTracker 等）での再生確認はまだ行っていない。

XM_ID = b"Extended Module: "        # 17 byte 固定
XM_TRACKER_NAME = "ModWeaver"
XM_VERSION = 0x0104                  # 1.04
XM_ORDER_TABLE_SIZE = 256
# header_size は「header_size フィールド自身（offset 60、4byte）を含めて」pattern order table の
# 終端までの長さとして書く（実プレイヤーは pattern データの開始位置を 60 + header_size として求める
# 規約——これが真の FT2/XM 仕様。以前は header_size フィールド自身を含めない 272 を書いていたため、
# 実プレイヤー側は常に 4byte 手前からパターンデータを読み始めてしまい、パターン内容が全て文字化け
# （OpenMPT で「パターンが空に見える」）していた。内部の parse_xm は独自規約で読んでいたため
# 自己ラウンドトリップ検査ではこのズレを検出できなかった＝実プレイヤーでの検証が必須だった好例）。
# header_size自身(4byte) + song_length/restart/n_channels/n_patterns/n_instruments/flags/tempo/bpm
# の8フィールド(各2byte=16byte) + order table(256byte) = 276。
XM_HEADER_SIZE = 4 + 8 * 2 + XM_ORDER_TABLE_SIZE   # = 276
XM_INSTRUMENT_HEADER_SIZE = 243       # sample 1個・エンベロープ無しの標準サイズ
XM_SAMPLE_HEADER_SIZE = 40
XM_MAX_INSTRUMENTS = 128
XM_FINETUNE_SCALE = 16                # MOD finetune(-8..7) を XM finetune(-128..127 相当) へ変換する倍率


def _xm_text(text: str, limit: int, what: str) -> bytes:
    """XM の名前系フィールド（空白パディングが慣習）。"""
    if len(text) > limit or not text.isascii():
        raise PlanError(f"{what} must be ASCII and <= {limit} chars: {text!r}")
    return text.encode("ascii").ljust(limit, b" ")


def _xm_cell_effect(cell: Cell) -> tuple[int, int]:
    """``vol`` は XM でも effect=0xC（Set Volume）へ変換する（MOD の Cell.serialize() と同じ解決）。
    XM 独自の volume column は使わない（CORE_EXTENSION_DESIGN §4.6③ のスコープどおり）。"""
    return (0xC, cell.vol) if cell.vol is not None else (cell.effect, cell.param)


def _pack_xm_cell(cell: Cell) -> bytes:
    """XM のパック済みセル形式（bit7=圧縮フラグ、bit0..4=note/instrument/vol/effect_type/effect_param
    の有無）。vol column（bit2）は常に立てない。"""
    note = 0 if cell.note is None else cell.note + 1     # 0=無音。t=0..35 -> XM note 1..36
    instrument = cell.sample                              # 0=無音のまま一致
    effect, param = _xm_cell_effect(cell)

    flags = 0
    body = bytearray()
    if note:
        flags |= 0x01
        body.append(note)
    if instrument:
        flags |= 0x02
        body.append(instrument)
    if effect or param:
        flags |= 0x08 | 0x10
        body.append(effect)
        body.append(param)
    return bytes([0x80 | flags]) + bytes(body)


def _pack_xm_pattern(pat: Pattern) -> bytes:
    out = bytearray()
    for r in range(pat.rows):
        for c in range(pat.channels):
            out += _pack_xm_cell(pat.get(r, c))
    return bytes(out)


def _serialize_xm_pattern(pat: Pattern) -> bytes:
    packed = _pack_xm_pattern(pat)
    if pat.rows > 256:
        raise PlanError(f"XM pattern rows must be <= 256: {pat.rows}")
    header = struct.pack("<IBHH", 9, 0, pat.rows, len(packed))
    return header + packed


def _xm_delta_encode(data: bytes) -> bytes:
    """XM の 8bit サンプルは差分（累積前サンプルとの差）符号化が必須。"""
    out = bytearray(len(data))
    prev = 0
    for i, b in enumerate(data):
        out[i] = (b - prev) & 0xFF
        prev = b
    return bytes(out)


def _xm_finetune(mod_finetune: int) -> int:
    """MOD finetune（-8..7）を XM finetune（概ね -128..127）へ比例変換する。"""
    return max(-128, min(127, mod_finetune * XM_FINETUNE_SCALE))


def _serialize_xm_instrument(spec: SampleSpec) -> bytes:
    """1 instrument = 1 sample（キーマップは全音で sample 0 を指す。エンベロープ無し）。"""
    spec.validate()
    name = _xm_text(spec.name, 22, "instrument name")

    header = bytearray()
    header += struct.pack("<I", XM_INSTRUMENT_HEADER_SIZE)
    header += name
    header += bytes([0])                          # instrument type（未使用）
    header += struct.pack("<H", 1)                 # number of samples = 1
    header += struct.pack("<I", XM_SAMPLE_HEADER_SIZE)
    header += bytes(96)                            # sample keymap: 全音 sample 0
    header += bytes(48)                             # volume envelope points（無効）
    header += bytes(48)                             # panning envelope points（無効）
    header += bytes([0, 0, 0, 0, 0, 0, 0, 0, 0, 0])  # n_vol_pts,n_pan_pts,各 sustain/loop点,vol/pan type
    header += bytes([0, 0, 0, 0])                    # vibrato type/sweep/depth/rate
    header += struct.pack("<H", 0)                   # volume fadeout
    header += struct.pack("<H", 0)                   # reserved
    assert len(header) == XM_INSTRUMENT_HEADER_SIZE, len(header)

    loop_start_words, loop_len_words = spec.loop_header
    has_loop = spec.loop is not None
    sample_header = bytearray()
    sample_header += struct.pack("<I", len(spec.data))                    # length（バイト）
    sample_header += struct.pack("<I", loop_start_words * 2 if has_loop else 0)
    sample_header += struct.pack("<I", loop_len_words * 2 if has_loop else 0)
    sample_header += bytes([spec.volume & 0xFF])
    sample_header += struct.pack("<b", _xm_finetune(spec.finetune))
    sample_header += bytes([1 if has_loop else 0])                        # sample type: bit0-1=loop種別、bit4=0(8bit)
    sample_header += bytes([spec.pan & 0xFF])
    sample_header += struct.pack("<b", 0)                                  # relative note number
    sample_header += bytes([0])                                            # reserved
    sample_header += _xm_text(spec.name, 22, "sample name")
    assert len(sample_header) == XM_SAMPLE_HEADER_SIZE, len(sample_header)

    return bytes(header) + bytes(sample_header) + _xm_delta_encode(spec.data)


def serialize_xm(song: Song) -> bytes:
    """Song を FastTracker II ``.xm`` 形式のバイト列へ変換する（EXT-6）。"""
    if not 1 <= len(song.order) <= ORDER_TABLE_SIZE:
        raise PlanError(f"order length must be 1..{ORDER_TABLE_SIZE}: {len(song.order)}")
    if len(song.samples) > XM_MAX_INSTRUMENTS:
        raise PlanError(f"too many instruments: {len(song.samples)} > {XM_MAX_INSTRUMENTS}")
    if not song.order or min(song.order) < 0:
        raise PlanError(f"negative pattern number in order: {song.order}")
    n_patterns = max(song.order) + 1
    if n_patterns > len(song.patterns):
        raise PlanError(
            f"order refers to pattern {n_patterns - 1} but only {len(song.patterns)} patterns exist"
        )
    n_channels = song.patterns[0].channels if song.patterns else 0
    if not 1 <= n_channels <= XM_MAX_CHANNELS:
        raise PlanError(f"XM channel count must be 1..{XM_MAX_CHANNELS}: {n_channels}")

    out = bytearray()
    out += XM_ID
    out += _xm_text(song.title, 20, "title")
    out += bytes([0x1A])
    out += _xm_text(XM_TRACKER_NAME, 20, "tracker name")
    out += struct.pack("<H", XM_VERSION)
    out += struct.pack("<I", XM_HEADER_SIZE)
    out += struct.pack("<H", len(song.order))       # song length
    out += struct.pack("<H", 0)                       # restart position
    out += struct.pack("<H", n_channels)
    out += struct.pack("<H", n_patterns)
    out += struct.pack("<H", len(song.samples))       # number of instruments
    out += struct.pack("<H", 1)                        # flags: bit0=1 -> linear frequency table
    out += struct.pack("<H", 6)                         # default speed（ticks/row）
    out += struct.pack("<H", 125)                        # default bpm（実テンポは Cell の Fxx が支配する）
    order_table = bytes(song.order) + bytes(XM_ORDER_TABLE_SIZE - len(song.order))
    out += order_table

    for pat in song.patterns[:n_patterns]:
        out += _serialize_xm_pattern(pat)
    for spec in song.samples:
        out += _serialize_xm_instrument(spec)
    return bytes(out)


def write_file(path: Union[str, Path], data: bytes) -> None:
    """同一ディレクトリの一時ファイルへ書き、``os.replace`` で置換する。

    Windows でも既存ファイルを置換できる。失敗時は一時ファイルを削除して ``OutputError``。
    """
    target = Path(path)
    tmp = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    try:
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, target)
    except OSError as e:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise OutputError(f"cannot write {target}: {e}") from e


# 出力フォーマット名 → シリアライザ
WRITERS: dict[str, Callable[[Song], bytes]] = {"mod": serialize, "xm": serialize_xm}
