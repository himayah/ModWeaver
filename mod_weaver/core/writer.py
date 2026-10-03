"""ProTracker ``M.K.``（＋FastTracker 系の多チャンネル ``xCHN``）のシリアライザ、FastTracker II ``.xm`` の定数、
原子的書込（DESIGN.md §7.2・§7.3）。

XM の書き出しは ``core/native_xm.py``（Realizer の ``RealizedSong`` から）。出力形式の一覧は ``core/formats.py``。
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
# DESIGN.md §7.3 のスコープどおり、エンベロープ／複数サンプルキーマップ／XM 独自の
# vol column は使わない（1 Instrument = 1 sample、Cell の vol/effect 排他制約をそのまま流用）。
#
# DESIGN_HISTORY.md §8: OpenMPT でパターン内容が読めない不具合を実際に検出・修正済み（header_size の
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
# tracker note t（0=ProTracker C-1＝period 856）→ XM note 番号（1始まり、1=C-0）への加算値。
# period 856 は FT2 の C-3（XM note 37）に相当する（FT2 の C-4＝note 49 が period 428／8363Hz）。
# 以前は t+1（C-0）と書いていたため 3 オクターブ低く鳴っていた。parse_xm も同じ誤った規約で読んでいたので
# 自己ラウンドトリップでは検出できず、libopenmpt で MOD と XM を実際に再生比較して発覚した
# （DESIGN_HISTORY.md §8。tests/realplayer/ の形式間等価性テストが回帰を防ぐ）。
XM_NOTE_OFFSET = 37


def _xm_text(text: str, limit: int, what: str) -> bytes:
    """XM の名前系フィールド（空白パディングが慣習）。"""
    if len(text) > limit or not text.isascii():
        raise PlanError(f"{what} must be ASCII and <= {limit} chars: {text!r}")
    return text.encode("ascii").ljust(limit, b" ")


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
