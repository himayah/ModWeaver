"""出力形式の能力表とチャンネルパンの決定（FORMAT_TEMPO_DESIGN §2）。

``engine.compose_song()`` が作る ``Song``（Cell＝MOD 風のエフェクト表現）を形式中立の中間表現として扱い、
形式ごとの差はすべて各シリアライザが吸収する。作曲ロジック（profiles/*）は出力形式を一切意識しない。

``FORMATS`` は形式名（CLI の ``--format`` の値）→ ``OutputFormat`` の表。各形式のシリアライザは
``(Song, WriteOptions) -> bytes`` に揃えてある（mp3 も外部ツールの出力をバイト列で返す）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Mapping, Optional, Sequence

from ..errors import PlanError
from .model import ChannelPlan, SampleSpec, Song

DEFAULT_FORMAT = "mod"

# §2.3: 明示的なパン指定が無い 4ch 系ジャンルを MOD 以外で出すときの Amiga 風 L R R L 配置。
# 0/255 の完全分離は耳障りなので 64/192 に緩める。
AMIGA_LEFT, AMIGA_RIGHT = 64, 192
CENTER = 128


@dataclass(frozen=True)
class WriteOptions:
    """プロファイル由来の、形式中立な付帯情報（Song 本体には持たせない）。"""
    channel_pans: tuple[int, ...]              # 0=左、128=中央、255=右（チャンネルごと）
    initial_bpm: int = 125                      # ヘッダの初期テンポ（先頭 row の Fxx を読まないプレイヤー対策）
    instrument_names: tuple[str, ...] = ()      # build_samples() の挿入順＝sample 番号順（MIDI の音色表引き用）
    gm_voices: Mapping[str, object] = field(default_factory=dict)   # 楽器名 → midi.GmVoice（MIDI のみ使用）
    rows_per_measure: int = 16                  # MIDI の拍子（可変拍子は measure_rows で上書き）
    measure_rows: tuple[tuple[int, ...], ...] = ()   # pattern ごとの小節長（row）列。空なら rows_per_measure 固定


@dataclass(frozen=True)
class OutputFormat:
    name: str                                   # CLI の値
    extension: str                              # ".mod" など（midi だけ名前と拡張子が違う）
    max_channels: int
    serialize: Callable[[Song, WriteOptions], bytes]
    verify: Optional[Callable[..., list]] = None   # (bytes, ChannelPlan) -> list[Issue]
    description: str = ""


def check_channels(fmt: OutputFormat, n_channels: int, where: str) -> None:
    if not 1 <= n_channels <= fmt.max_channels:
        raise PlanError(f"{where}: {n_channels} channels not supported by format {fmt.name!r} "
                        f"(1..{fmt.max_channels})")


def channel_pans(song: Song, declared: Optional[Sequence[int]] = None) -> tuple[int, ...]:
    """§2.3 の規則でチャンネルごとのパンを決める。

    1. プロファイルの宣言（``GenreProfile.channel_pans``）があればそれ
    2. 全サンプルが既定パン（128）なら Amiga 風 L R R L の繰り返し（64/192）
    3. 明示パンのあるサンプルがあれば、各チャンネルで再生順に最初に鳴るサンプルの pan（鳴らなければ中央）
    """
    n = song.patterns[0].channels if song.patterns else 0
    if declared is not None:
        if len(declared) != n or any(not 0 <= p <= 255 for p in declared):
            raise PlanError(f"channel_pans must have {n} values in 0..255: {tuple(declared)}")
        return tuple(declared)
    if all(s.pan == CENTER for s in song.samples):
        return tuple(AMIGA_LEFT if ch % 4 in (0, 3) else AMIGA_RIGHT for ch in range(n))
    return tuple(_first_sample_pan(song, ch) for ch in range(n))


def _first_sample_pan(song: Song, ch: int) -> int:
    for p in song.order:
        pat = song.patterns[p]
        for r in range(pat.rows):
            cell = pat.get(r, ch)
            if cell.sample:
                return song.samples[cell.sample - 1].pan
    return CENTER


def sample_has_default_pan(spec: SampleSpec) -> bool:
    return spec.pan == CENTER


def _registry() -> dict[str, OutputFormat]:
    # 各形式モジュールは formats を import するため、循環を避けて遅延 import する。
    from . import it, midi, render, s3m, verify, writer

    formats = [
        OutputFormat("mod", ".mod", writer.MOD_MAX_CHANNELS, writer.serialize_with_options, verify.verify,
                     "ProTracker MOD (4ch: M.K.; other channel counts: FastTracker xCHN)"),
        OutputFormat("xm", ".xm", writer.XM_MAX_CHANNELS, writer.serialize_xm_with_options, verify.verify_xm,
                     "FastTracker II Extended Module"),
        OutputFormat("s3m", ".s3m", s3m.MAX_CHANNELS, s3m.serialize_s3m, s3m.verify_s3m, "Scream Tracker 3"),
        OutputFormat("it", ".it", it.MAX_CHANNELS, it.serialize_it, it.verify_it, "Impulse Tracker"),
        OutputFormat("midi", ".mid", midi.MAX_CHANNELS, midi.serialize_midi, midi.verify_midi,
                     "Standard MIDI File (General MIDI)"),
        OutputFormat("mp3", ".mp3", render.MAX_CHANNELS, render.render_mp3, None,
                     "MP3 audio (requires ffmpeg with libopenmpt and libmp3lame)"),
    ]
    return {f.name: f for f in formats}


_FORMATS: Optional[dict[str, OutputFormat]] = None


def get_formats() -> dict[str, OutputFormat]:
    global _FORMATS
    if _FORMATS is None:
        _FORMATS = _registry()
    return _FORMATS


def get_format(name: str) -> OutputFormat:
    try:
        return get_formats()[name]
    except KeyError:
        raise PlanError(f"unknown format {name!r}. choices: {', '.join(get_formats())}") from None


def format_names() -> tuple[str, ...]:
    return tuple(get_formats())
