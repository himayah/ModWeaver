"""ProTracker ``M.K.``（＋FastTracker 系の多チャンネル ``xCHN``）および FastTracker II ``.xm``
シリアライザと原子的書込（設計書 §6.3、CORE_EXTENSION_DESIGN §4.6③ EXT-6、FORMAT_TEMPO_DESIGN §4.1・§4.2）。

出力形式の一覧は ``core/formats.py`` の ``FORMATS``。
"""
from __future__ import annotations

import os
import struct
from pathlib import Path
from typing import Optional, Sequence, Union

from ..errors import OutputError, PlanError
from .model import Cell, Pattern, SampleSpec, Song

HEADER_SAMPLES = 31
ORDER_TABLE_SIZE = 128
TITLE_SIZE = 20
MAGIC = b"M.K."
MOD_MAX_CHANNELS = 32  # 4 以外は FastTracker 系の "xCHN"/"xxCH"（本家 ProTracker/Amiga では再生不可）

XM_MAX_CHANNELS = 32   # target_format != "mod" のプロファイルが宣言できる channel_plan の上限


def _ascii_bytes(text: str, limit: int, what: str) -> bytes:
    if len(text) > limit or not text.isascii():
        raise PlanError(f"{what} must be ASCII and <= {limit} chars: {text!r}")
    return text.encode("ascii")


def mod_magic(n_channels: int) -> bytes:
    """4ch は ``M.K.``、1..9ch は ``"{n}CHN"``、10..32ch は ``"{n}CH"``（FastTracker/OpenMPT/libxmp 対応）。"""
    if not 1 <= n_channels <= MOD_MAX_CHANNELS:
        raise PlanError(f"MOD channel count must be 1..{MOD_MAX_CHANNELS}: {n_channels}")
    if n_channels == 4:
        return MAGIC
    return f"{n_channels}CHN".encode() if n_channels < 10 else f"{n_channels}CH".encode()


def serialize(song: Song) -> bytes:
    """Song を MOD 形式のバイト列へ変換する（4ch は ``M.K.``、それ以外は ``xCHN``）。"""
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
    out += mod_magic(song.patterns[0].channels if song.patterns else 4)

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
# §11 の要検証事項: OpenMPT でパターン内容が読めない不具合を実際に検出・修正済み（header_size の
# 基準オフセット、下記 XM_HEADER_SIZE のコメント参照）。波形・パンニングの実プレイヤーでの聴感確認は
# まだ未実施。

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
# tracker note t（0=ProTracker C-1＝period 856）→ XM note 番号（1始まり、1=C-0）への加算値。
# period 856 は FT2 の C-3（XM note 37）に相当する（FT2 の C-4＝note 49 が period 428／8363Hz）。
# 以前は t+1（C-0）と書いていたため 3 オクターブ低く鳴っていた。parse_xm も同じ誤った規約で読んでいたので
# 自己ラウンドトリップでは検出できず、libopenmpt で MOD と XM を実際に再生比較して発覚した
# （FORMAT_TEMPO_DESIGN §1.1。tests/realplayer/ の形式間等価性テストが回帰を防ぐ）。
XM_NOTE_OFFSET = 37


def _xm_text(text: str, limit: int, what: str) -> bytes:
    """XM の名前系フィールド（空白パディングが慣習）。"""
    if len(text) > limit or not text.isascii():
        raise PlanError(f"{what} must be ASCII and <= {limit} chars: {text!r}")
    return text.encode("ascii").ljust(limit, b" ")


def _xm_cell_effect(cell: Cell) -> tuple[int, int]:
    """``vol`` は XM でも effect=0xC（Set Volume）へ変換する（MOD の Cell.serialize() と同じ解決）。
    XM 独自の volume column は使わない（CORE_EXTENSION_DESIGN §4.6③ のスコープどおり）。"""
    return (0xC, cell.vol) if cell.vol is not None else (cell.effect, cell.param)


def _pack_xm_cell(cell: Cell, pan: Optional[int] = None) -> bytes:
    """XM のパック済みセル形式（bit7=圧縮フラグ、bit0..4=note/instrument/vol/effect_type/effect_param
    の有無）。vol column（bit2）はチャンネルパン（``pan``、0..255）の ``Px`` にだけ使う。"""
    note = 0 if cell.note is None else cell.note + XM_NOTE_OFFSET   # 0=無音。t=0..35 -> XM note 37..72
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
    if pan is not None:
        flags |= 0x04
        body.append(0xC0 | (pan >> 4))                    # vol column Px: Set Panning（0..F）
    if effect or param:
        flags |= 0x08 | 0x10
        body.append(effect)
        body.append(param)
    return bytes([0x80 | flags]) + bytes(body)


def _pack_xm_pattern(pat: Pattern, pan_for: Sequence[Optional[int]], default_pan: Sequence[bool]) -> bytes:
    """``pan_for[c]``: チャンネル c のパン（None なら書かない）。``default_pan[i]``: sample i+1 が既定パンか。

    XM は instrument 番号付きのセルでチャンネルパンがサンプル既定値に戻るため、既定パン（128）の
    サンプルを鳴らすセルにだけ毎回 ``Px`` を付けてチャンネルパンを再設定する（FORMAT_TEMPO_DESIGN §4.2）。"""
    out = bytearray()
    for r in range(pat.rows):
        for c in range(pat.channels):
            cell = pat.get(r, c)
            known = 0 < cell.sample <= len(default_pan)       # 未定義番号は verify の V06 に任せ、ここでは書くだけ
            pan = pan_for[c] if known and default_pan[cell.sample - 1] else None
            out += _pack_xm_cell(cell, pan)
    return bytes(out)


def _serialize_xm_pattern(pat: Pattern, pan_for: Sequence[Optional[int]], default_pan: Sequence[bool]) -> bytes:
    packed = _pack_xm_pattern(pat, pan_for, default_pan)
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


def serialize_xm(
    song: Song, *, channel_pans: Optional[Sequence[int]] = None, initial_bpm: int = 125,
) -> bytes:
    """Song を FastTracker II ``.xm`` 形式のバイト列へ変換する（EXT-6）。

    ``channel_pans`` を渡すと、既定パン（128）のサンプルを鳴らすセルにチャンネルパンを付ける
    （省略時は従来どおりサンプルパンのみ）。``initial_bpm`` はヘッダの初期テンポ。"""
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
    out += struct.pack("<H", 0)                        # flags: bit0=0 -> Amiga frequency table
    # ↑ MOD と同じ Amiga period 単位で 1xx/2xx/3xx が効く（automation.portamento_param は period 基準で
    #   param を計算している。linear table だとグライドの速さが変わる）
    out += struct.pack("<H", 6)                         # default speed（ticks/row）
    out += struct.pack("<H", initial_bpm)                # default bpm（実テンポは Cell の Fxx が支配する）
    order_table = bytes(song.order) + bytes(XM_ORDER_TABLE_SIZE - len(song.order))
    out += order_table

    pan_for = list(channel_pans) if channel_pans is not None else [None] * n_channels
    default_pan = [s.pan == 128 for s in song.samples]
    for pat in song.patterns[:n_patterns]:
        out += _serialize_xm_pattern(pat, pan_for, default_pan)
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


# ---- core/formats.py の OutputFormat.serialize 用アダプタ（(Song, WriteOptions) -> bytes） ----

def serialize_with_options(song: Song, opts) -> bytes:
    """MOD はチャンネルパン（プレイヤー固定）・初期テンポ（ヘッダに欄が無い）を持たない。"""
    return serialize(song)


def serialize_xm_with_options(song: Song, opts) -> bytes:
    return serialize_xm(song, channel_pans=opts.channel_pans, initial_bpm=opts.initial_bpm)
