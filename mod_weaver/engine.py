"""生成エンジン（DESIGN.md §2.1）。

``Genre`` の ``plan()`` → ジェネレータ（``framework.compose``）で形式に依存しない ``Score`` を作り、
形式ごとの Realizer（トラッカー系は ``framework.realize.tracker``、MIDI は ``framework.realize.midi``）でバイト列にし、
検査器（``core.native``）で確かめて書き出す。MP3 は IT を作って ffmpeg（libopenmpt）で符号化する。
エンジンが所有する処理: ``--tempo`` の確定、形式・チャンネル数の確定（``framework.target``）、検査、書込。
"""
from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union

from .core import formats, native, render, writer
from .core import verify as verify_mod
from .errors import ChannelCountError, TempoRangeError, VerificationError
from .framework import registry
from .framework.compose import compose, resolve_plan
from .framework.genre import Genre
from .framework.plan import SongPlan
from .framework.realize.midi import realize_midi
from .framework.realize.tracker import realize
from .framework.score import Score
from .framework.target import Target, resolve

log = logging.getLogger("mod_weaver")

registry.discover("mod_weaver.genres")   # ジャンルモジュールを import して登録する

SEED_RANGE = (100000, 999999)   # seed 省略時の乱数範囲（旧仕様どおり）
TEMPO_MIN, TEMPO_MAX = 32, 255  # Fxx が Tempo と解釈される範囲（31 以下は Speed になる）


@dataclass(frozen=True)
class TempoRequest:
    """``--tempo`` の要求（単一値は ``lo == hi``）。DESIGN.md §5.5。"""
    lo: int
    hi: int

    def __post_init__(self) -> None:
        if not TEMPO_MIN <= self.lo <= self.hi <= TEMPO_MAX:
            raise ValueError(f"tempo must satisfy {TEMPO_MIN} <= MIN <= MAX <= {TEMPO_MAX}: {self}")

    @classmethod
    def parse(cls, text: str) -> "TempoRequest":
        """``"120"`` または ``"80-100"``。不正は ValueError。"""
        parts = text.strip().split("-")
        if len(parts) not in (1, 2) or not all(p.strip().isdigit() for p in parts):
            raise ValueError(f"invalid tempo {text!r} (expected BPM or MIN-MAX, e.g. 120 or 80-100)")
        lo, hi = int(parts[0]), int(parts[-1])
        return cls(lo, hi)

    def __str__(self) -> str:
        return str(self.lo) if self.lo == self.hi else f"{self.lo}-{self.hi}"


@dataclass
class Built:
    """``build()`` の結果（I/O なし）。"""
    genre: Genre
    seed: int
    fmt: str
    plan: SongPlan
    score: Score
    target: Target
    data: bytes
    channels: int                         # 実際に使ったチャンネル数（MIDI は鳴らした MIDI チャンネルの数）
    sample_bits: Optional[int]            # サンプルのビット数（MIDI は None）


@dataclass
class Result:
    seed: int
    path: Optional[Path]
    plan: SongPlan
    issues: list[verify_mod.Issue]
    genre: Genre
    tempo_request: Optional[TempoRequest] = None
    fmt: str = formats.DEFAULT_FORMAT
    channels_request: Optional[int] = None
    channels: int = 0
    channel_budget: int = 0
    sample_bits: Optional[int] = None


# ------------------------------------------------------------
# ジャンルの引き方
# ------------------------------------------------------------

def get_genre(name: str) -> Genre:
    """id または別名からジャンルを取る（未登録は ``ProfileNotFoundError``）。"""
    return registry.get_genre(name)


def list_genres() -> list[Genre]:
    return [cls() for cls in registry.list_genres()]


def channel_choices(genre: Genre) -> tuple[int, ...]:
    """MOD でジャンルが選べるチャンネル数。"""
    return tuple(sorted(genre.mod_channels))


# ------------------------------------------------------------
# テンポ
# ------------------------------------------------------------

def resolve_tempo(request: TempoRequest, seed: int, genre: Genre) -> int:
    """``--tempo`` の要求をジャンルの ``tempo_range`` と突き合わせ、BPM を1つに確定する（DESIGN.md §5.5）。

    一部だけ重なる場合は重なり部分へ切り詰めて WARNING、重ならなければ ``TempoRangeError``。
    範囲からの選択は専用ストリームで行い、他の乱数消費を一切変えない。
    """
    lo, hi = max(request.lo, genre.tempo_range[0]), min(request.hi, genre.tempo_range[1])
    if lo > hi:
        allowed = f"{genre.tempo_range[0]}-{genre.tempo_range[1]}"
        raise TempoRangeError(f"tempo {request} is outside the range genre {genre.id!r} supports ({allowed})")
    if (lo, hi) != (request.lo, request.hi):
        log.warning("tempo %s clipped to %s-%s (genre %r supports %s-%s)",
                    request, lo, hi, genre.id, *genre.tempo_range)
    return random.Random(f"{seed}:{genre.id}:tempo").randint(lo, hi)


# ------------------------------------------------------------
# 生成
# ------------------------------------------------------------

def supports_channels(genre: Genre, fmt: str, channels: int, seed: int) -> bool:
    """``--channels`` の値でこのジャンルをこの形式で作れるか（``--genre random`` の候補の絞り込み用）。"""
    try:
        target = resolve(fmt, channels, genre, seed)
        if target.kind == "tracker" and fmt != "mod":
            from .framework.realize import lanes as lanesmod

            plan = resolve_plan(genre, seed)
            lanesmod.compute_layout(genre, compose(genre, plan, seed, target.features), target.budget)
    except ChannelCountError:
        return False
    return True


def _midi_channels(data: bytes) -> int:
    from .core.midi import parse_midi

    used = {m[0] & 0x0F for track in parse_midi(data).tracks for _t, m in track
            if m and 0x90 <= m[0] <= 0x9F and len(m) > 2 and m[2] > 0}
    return len(used)


def build(genre: Genre, seed: int, fmt: str = formats.DEFAULT_FORMAT, *, tempo: Optional[TempoRequest] = None,
          channels: Optional[int] = None) -> Built:
    """純粋関数（I/O なし。MP3 だけ ffmpeg を呼ぶ）。

    ``tempo`` を渡すと ``plan()`` が選んだ BPM を上書きする。``plan()`` 自体は従来どおり BPM を引く（引いた値を捨てる）ので
    他の乱数消費は変わらず、「同じ seed・別テンポ＝同じ曲の速さ違い」になる。"""
    target = resolve(fmt, channels, genre, seed)
    plan = resolve_plan(genre, seed)
    if tempo is not None:
        plan.bpm = resolve_tempo(tempo, seed, genre)
    log.debug("%s seed=%s fmt=%s bpm=%s sections=%d", genre.id, seed, fmt, plan.bpm, len(plan.order))
    score = compose(genre, plan, seed, target.features)

    if target.kind == "midi":
        data = realize_midi(genre, score, plan, target)
        return Built(genre, seed, fmt, plan, score, target, data, _midi_channels(data), None)
    rs = realize(genre, score, plan, target)
    module = native.serialize(rs)
    bits = rs.samples[0].bits if rs.samples else None
    if fmt == "mp3":
        data = render.render_mp3_from_it(module, genre.title)
    else:
        data = module
    return Built(genre, seed, fmt, plan, score, target, data, rs.n_channels, bits)


def verify_data(built: Built) -> list[verify_mod.Issue]:
    """出力の検査（MP3 は検査器が無い）。"""
    if built.fmt == "mp3":
        return []
    return native.verify(built.fmt, built.data)


def generate(
    genre: Genre,
    seed: Optional[int],
    out: Union[str, Path],
    *,
    verify: bool = True,
    tempo: Optional[TempoRequest] = None,
    fmt: str = formats.DEFAULT_FORMAT,
    channels: Optional[int] = None,
) -> Result:
    """曲を生成し、検査して ``fmt`` 形式（既定 mod）のファイルを書き出す。検査 ERROR があればファイルを書かない。"""
    if seed is None:
        seed = random.randint(*SEED_RANGE)
    built = build(genre, seed, fmt, tempo=tempo, channels=channels)

    issues: list[verify_mod.Issue] = []
    if verify:
        issues = verify_data(built)
        for i in issues:
            if i.level == "WARN":
                log.warning("%s %s", i.code, i.message)
            elif i.level == "INFO":
                log.info("%s %s", i.code, i.message)
        errors = [i for i in issues if i.level == "ERROR"]
        if errors:
            raise VerificationError(errors)

    path = Path(out)
    writer.write_file(path, built.data)
    return Result(seed=seed, path=path, plan=built.plan, issues=issues, genre=genre, tempo_request=tempo, fmt=fmt,
                  channels_request=channels, channels=built.channels, channel_budget=built.target.budget,
                  sample_bits=built.sample_bits)
