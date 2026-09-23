"""MP3 出力（DESIGN.md §7.8）。外部の ffmpeg に委譲する。

Song をいったん XM（任意チャンネル数・サンプルパン・チャンネルパンを保持できる形式）にし、ffmpeg 内蔵の
libopenmpt（OpenMPT の再生エンジン）で再生・libmp3lame で MP3 に符号化する。自前の再生エンジンは持たない
（音質・互換性は libopenmpt が最も高く、「自作 writer を自作 player で確かめる」自己一致の罠も避けられる）。

**実行環境に ffmpeg が必要**（libopenmpt と libmp3lame を有効にしてビルドされたもの）。PATH 上の
``ffmpeg``、または環境変数 ``MODWEAVER_FFMPEG`` で指定した実行ファイルを使う。Python の実行時依存は増えない。
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path

from ..errors import ExternalToolError
from . import writer
from .model import Song

MAX_CHANNELS = writer.XM_MAX_CHANNELS
FFMPEG_ENV = "MODWEAVER_FFMPEG"
BITRATE = "192k"
SAMPLE_RATE = 44100
TIMEOUT_SEC = 600


def find_ffmpeg() -> str:
    """使う ffmpeg のパス。見つからなければ ExternalToolError。"""
    exe = os.environ.get(FFMPEG_ENV) or shutil.which("ffmpeg")
    if not exe:
        raise ExternalToolError(
            "mp3 output requires ffmpeg (built with libopenmpt and libmp3lame), but it was not found. "
            f"Install ffmpeg and put it on PATH, or set {FFMPEG_ENV} to its path."
        )
    return exe


@lru_cache(maxsize=8)
def _capabilities(exe: str) -> tuple[bool, bool]:
    def listing(flag: str) -> str:
        try:
            return subprocess.run([exe, "-hide_banner", flag], capture_output=True, text=True,
                                  timeout=60).stdout
        except (OSError, subprocess.SubprocessError) as e:
            raise ExternalToolError(f"cannot run ffmpeg ({exe}): {e}") from e
    return "libopenmpt" in listing("-demuxers"), "libmp3lame" in listing("-encoders")


def check_ffmpeg() -> str:
    """ffmpeg が MP3 生成に必要な機能を持つか検査し、パスを返す。"""
    exe = find_ffmpeg()
    has_openmpt, has_lame = _capabilities(exe)
    missing = [name for name, ok in (("libopenmpt", has_openmpt), ("libmp3lame", has_lame)) if not ok]
    if missing:
        raise ExternalToolError(
            f"ffmpeg at {exe} lacks {' and '.join(missing)}, which mp3 output needs. "
            "Use an ffmpeg build that includes them (e.g. a 'full' build)."
        )
    return exe


def render_mp3(song: Song, opts) -> bytes:
    """Song を MP3 のバイト列にする。``opts`` は ``formats.WriteOptions``。"""
    exe = check_ffmpeg()
    xm = writer.serialize_xm(song, channel_pans=opts.channel_pans, initial_bpm=opts.initial_bpm)
    with tempfile.TemporaryDirectory(prefix="modweaver-") as d:
        src, dst = Path(d) / "song.xm", Path(d) / "song.mp3"
        src.write_bytes(xm)
        cmd = [exe, "-hide_banner", "-nostdin", "-loglevel", "error", "-y",
               "-f", "libopenmpt", "-i", str(src),
               "-ar", str(SAMPLE_RATE), "-c:a", "libmp3lame", "-b:a", BITRATE,
               "-metadata", f"title={song.title}", "-metadata", "encoder=ModWeaver",
               str(dst)]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT_SEC)
        except (OSError, subprocess.SubprocessError) as e:
            raise ExternalToolError(f"ffmpeg failed to run: {e}") from e
        if proc.returncode != 0 or not dst.exists():
            raise ExternalToolError(f"ffmpeg failed (exit {proc.returncode}): {proc.stderr.strip()[:500]}")
        return dst.read_bytes()
