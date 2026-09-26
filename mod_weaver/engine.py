"""生成エンジン（DESIGN.md §2.3、§5）。

エンジンが所有する処理: テンポセル挿入、pattern への転記、順序表、バイト化、検査、書込。
プロファイルが所有する処理: 音色、和声、リズム、フレーズ、パート間の音の配置。
"""
from __future__ import annotations

import dataclasses
import logging
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

from .core import formats, level, writer
from .core import verify as verify_mod
from .core.model import (
    MAX_SAMPLES,
    ROWS_PER_PATTERN,
    Instrument,
    MeasureBuffer,
    MeasureCtx,
    Pattern,
    PatternCtx,
    RngStreams,
    Song,
    SongPlan,
)
from .errors import ChannelCountError, PlanError, SampleConstraintError, TempoRangeError, VerificationError
from .profiles.base import GenreProfile
from .profiles.levels import PEAK_DB

log = logging.getLogger("mod_weaver")

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
class Result:
    seed: int
    path: Optional[Path]
    song: Song
    plan: SongPlan
    issues: list[verify_mod.Issue]
    tempo_request: Optional[TempoRequest] = None
    fmt: str = formats.DEFAULT_FORMAT
    channels_request: Optional[int] = None


# ------------------------------------------------------------
# 契約検査（DESIGN.md §5.4）
# ------------------------------------------------------------

def validate_timebase(rows_per_measure: int) -> None:
    """小節長の制約。現行は「64 の約数」。``variable_meter=True`` のプロファイルはこの検査を
    スキップする（``ChordSlot.rows`` で measure ごとに行数を上書きできるため。EXT-2）。"""
    if rows_per_measure <= 0 or ROWS_PER_PATTERN % rows_per_measure != 0:
        raise PlanError(f"rows_per_measure must divide {ROWS_PER_PATTERN}: {rows_per_measure}")


MAX_PROFILE_CHANNELS = 64   # プロファイルが宣言できる上限（形式ごとの上限は formats.OutputFormat.max_channels）


def validate_profile(profile: GenreProfile) -> None:
    """形式に依存しない宣言の検査。形式ごとのチャンネル数上限は ``generate()`` が
    ``formats.check_channels`` で検査する（DESIGN.md §7.1）。"""
    if profile.variable_meter:
        if profile.rows_per_measure <= 0:
            raise PlanError(f"{profile.id}: rows_per_measure must be positive: {profile.rows_per_measure}")
    else:
        validate_timebase(profile.rows_per_measure)
    if not 1 <= len(profile.channel_plan) <= MAX_PROFILE_CHANNELS:
        raise PlanError(f"{profile.id}: channel_plan must have 1..{MAX_PROFILE_CHANNELS} roles")
    if any(not 1 <= n <= MAX_PROFILE_CHANNELS for n in profile.channel_choices):
        raise PlanError(f"{profile.id}: channel_choices must be within 1..{MAX_PROFILE_CHANNELS}")
    if profile.tempo_policy not in ("engine", "profile"):
        raise PlanError(f"{profile.id}: invalid tempo_policy {profile.tempo_policy!r}")
    if profile.rng_mode not in ("single", "streams"):
        raise PlanError(f"{profile.id}: invalid rng_mode {profile.rng_mode!r}")
    lo, hi = profile.tempo_range
    if not TEMPO_MIN <= lo <= hi <= TEMPO_MAX:
        raise PlanError(f"{profile.id}: tempo_range must be within {TEMPO_MIN}..{TEMPO_MAX}: {profile.tempo_range}")
    if any(not lo <= b <= hi for b in profile.tempo_choices):
        raise PlanError(f"{profile.id}: tempo_choices {profile.tempo_choices} outside tempo_range {profile.tempo_range}")
    if len(profile.title) > 20 or not profile.title.isascii():
        raise PlanError(f"{profile.id}: title must be ASCII and <= 20 chars: {profile.title!r}")


def validate_plan(profile: GenreProfile, plan: SongPlan, *, tempo_overridden: bool = False) -> None:
    where = f"[{profile.id}]"
    if tempo_overridden:
        lo, hi = profile.tempo_range
        if not lo <= plan.bpm <= hi:
            raise PlanError(f"{where} bpm {plan.bpm} outside tempo_range {profile.tempo_range}")
    elif plan.bpm not in profile.tempo_choices:
        raise PlanError(f"{where} bpm {plan.bpm} not in tempo_choices {profile.tempo_choices}")
    if not plan.patterns:
        raise PlanError(f"{where} plan has no patterns")
    for i, pp in enumerate(plan.patterns):
        if any(s.measures < 1 for s in pp.slots):
            raise PlanError(f"{where} pattern {i} ({pp.kind}): slot with measures < 1")
        total = sum((s.rows if s.rows is not None else profile.rows_per_measure) * s.measures for s in pp.slots)
        if profile.variable_meter:
            if not 1 <= total <= ROWS_PER_PATTERN:
                raise PlanError(
                    f"{where} pattern {i} ({pp.kind}): slots cover {total} rows, must be 1..{ROWS_PER_PATTERN}"
                )
        elif total != ROWS_PER_PATTERN:
            raise PlanError(
                f"{where} pattern {i} ({pp.kind}): slots cover {total} rows, expected {ROWS_PER_PATTERN}"
            )
    if not 1 <= len(plan.order) <= 128:
        raise PlanError(f"{where} order length must be 1..128: {len(plan.order)}")
    bad = [o for o in plan.order if not 0 <= o < len(plan.patterns)]
    if bad:
        raise PlanError(f"{where} order refers to undefined pattern(s): {sorted(set(bad))}")
    if max(plan.order) + 1 > 64:
        raise PlanError(f"{where} too many patterns: {max(plan.order) + 1} > 64")


def make_instruments(profile: GenreProfile) -> tuple[list, dict[str, Instrument]]:
    """``build_samples`` の結果を検査し、sample 番号（挿入順=1..）付きの Instrument 表を作る。"""
    specs = profile.build_samples()
    if len(specs) > MAX_SAMPLES:
        raise SampleConstraintError(f"{profile.id}: too many samples: {len(specs)} > {MAX_SAMPLES}")
    for spec in specs.values():
        spec.validate()
    instruments = {name: Instrument(i, spec) for i, (name, spec) in enumerate(specs.items(), start=1)}
    return list(specs.values()), instruments


# ------------------------------------------------------------
# 生成
# ------------------------------------------------------------

def _make_rng(profile: GenreProfile, seed: int) -> Union[random.Random, RngStreams]:
    if profile.rng_mode == "single":
        return random.Random(seed)
    return RngStreams.for_seed(seed, profile.id)


def resolve_tempo(request: TempoRequest, seed: int, profile: GenreProfile) -> int:
    """``--tempo`` の要求をジャンルの ``tempo_range`` と突き合わせ、BPM を1つに確定する（DESIGN.md §5.5）。

    一部だけ重なる場合は重なり部分へ切り詰めて WARNING、重ならなければ ``TempoRangeError``。
    範囲からの選択は専用ストリーム（``RngStreams`` と同じ命名規約）で行い、他の乱数消費を一切変えない。
    """
    lo, hi = max(request.lo, profile.tempo_range[0]), min(request.hi, profile.tempo_range[1])
    if lo > hi:
        allowed = f"{profile.tempo_range[0]}-{profile.tempo_range[1]}"
        raise TempoRangeError(f"tempo {request} is outside the range genre {profile.id!r} supports ({allowed})")
    if (lo, hi) != (request.lo, request.hi):
        log.warning("tempo %s clipped to %s-%s (genre %r supports %s-%s)",
                    request, lo, hi, profile.id, *profile.tempo_range)
    return random.Random(f"{seed}:{profile.id}:tempo").randint(lo, hi)


def channel_choices(profile: GenreProfile) -> tuple[int, ...]:
    """ジャンルが選べるチャンネル数（固定のジャンルは宣言の数だけ）。"""
    return tuple(profile.channel_choices) or (len(profile.channel_plan),)


def resolve_channels(request: Optional[int], seed: int, profile: GenreProfile) -> int:
    """``--channels`` の要求を確かめ、無ければ seed から選ぶ（DESIGN.md §6.14）。

    選択は専用ストリーム（``RngStreams`` と同じ命名規約）で行い、他の乱数消費を一切変えない。"""
    choices = channel_choices(profile)
    if request is not None:
        if request not in choices:
            allowed = "/".join(map(str, choices))
            raise ChannelCountError(f"genre {profile.id!r} cannot use {request} channels (supports {allowed})")
        return request
    if len(choices) == 1:
        return choices[0]
    weights = [profile.channel_weights.get(n, 1) for n in choices]
    return random.Random(f"{seed}:{profile.id}:channels").choices(choices, weights=weights)[0]


def effective_channel_plan(profile: GenreProfile, plan: SongPlan):
    """曲の物理チャンネル構成（``arrange()`` が決めたもの、無ければジャンルの宣言）。"""
    return plan.channel_plan if plan.channel_plan is not None else profile.channel_plan


def apply_tempo(song: Song, bpm: int) -> None:
    """``order[0]`` の pattern の row 0 に ``F bpm`` を挿入する（tempo_policy="engine"）。

    探索・挿入は ``CellGrid.insert_command``（core/model.py。DESIGN.md §3.2・§4.10）に委譲する。
    空きチャンネルが無ければそちらが ChannelConflictError を送出する（プロファイルの不具合）。
    """
    song.patterns[song.order[0]].insert_command(0, 0x0F, bpm)


def compose_song(
    profile: GenreProfile, seed: int, *, tempo: Optional[TempoRequest] = None, channels: Optional[int] = None,
) -> tuple[Song, SongPlan]:
    """純粋関数（I/O なし）。Song と SongPlan を返す。

    ``tempo`` を渡すと ``plan()`` が選んだ BPM を上書きする。``plan()`` 自体は従来どおり BPM を引く
    （引いた値を捨てる）ので他の乱数消費は変わらず、「同じ seed・別テンポ＝同じ曲の速さ違い」になる。
    ``channels`` は曲のチャンネル数（``channel_choices`` を持つジャンルだけ。無ければ seed から選ぶ）。"""
    validate_profile(profile)
    n_channels = resolve_channels(channels, seed, profile)
    rng = _make_rng(profile, seed)

    specs, instruments = make_instruments(profile)
    plan = profile.plan(rng)
    if tempo is not None:
        plan = dataclasses.replace(plan, bpm=resolve_tempo(tempo, seed, profile))
    validate_plan(profile, plan, tempo_overridden=tempo is not None)
    log.debug("%s seed=%s bpm=%s patterns=%d order=%s", profile.id, seed, plan.bpm, len(plan.patterns), plan.order)

    rpm = profile.rows_per_measure
    patterns: list[Pattern] = []
    for idx, pp in enumerate(plan.patterns):
        pctx = PatternCtx(
            kind=pp.kind,
            index=idx,
            bpm=plan.bpm,
            key_pc=plan.key_pc,
            key_offset=pp.key_offset,
            intensity=pp.intensity,
            is_first_in_order=plan.order[0] == idx,
            extra=dict(pp.extra),
        )
        state = profile.begin_pattern(pctx, rng)
        pattern = Pattern(profile.channel_plan, profile.strict_buffers)
        n_measures = sum(s.measures for s in pp.slots)
        m = 0
        row = 0
        for slot in pp.slots:
            measure_rows = slot.rows if slot.rows is not None else rpm
            for k in range(slot.measures):
                mctx = MeasureCtx(
                    pattern=pctx,
                    measure_idx=m,
                    n_measures=n_measures,
                    chord=slot.chord,
                    chord_measure_offset=k,
                    is_last=(m == n_measures - 1),
                    instruments=instruments,
                    measure_rows=measure_rows,
                )
                buf = MeasureBuffer(measure_rows, profile.channel_plan, profile.strict_buffers)
                profile.compose_measure(mctx, state, rng, buf)
                pattern.blit(buf, row)
                row += measure_rows
                m += 1
        profile.finalize_pattern(pctx, pattern, state, rng)
        if profile.variable_meter and row < ROWS_PER_PATTERN:
            pattern.insert_command(row - 1, 0x0D, 0x00)   # D00: 次 pattern の row0 へ break
        patterns.append(pattern)

    song = Song(profile.title, specs, patterns, list(plan.order), instrument_names=tuple(instruments))
    if profile.channel_choices:
        plan = profile.arrange(song, plan, n_channels)
    physical = effective_channel_plan(profile, plan)
    if len(physical) != n_channels or any(p.channels != n_channels for p in song.patterns):
        raise PlanError(f"[{profile.id}] arrange() produced patterns that do not have {n_channels} channels")
    for post in profile.post_processors:
        post(song, plan)
    if profile.tempo_policy == "engine":
        apply_tempo(song, plan.bpm)
    return song, plan


def build_song(profile: GenreProfile, seed: int, *, tempo: Optional[TempoRequest] = None,
               channels: Optional[int] = None) -> Song:
    """純粋関数（I/O なし）。テストは Song／bytes を直接検査できる。"""
    return compose_song(profile, seed, tempo=tempo, channels=channels)[0]


def write_options(profile: GenreProfile, song: Song, plan: SongPlan) -> formats.WriteOptions:
    """形式中立な付帯情報（チャンネルパン・初期テンポ・MIDI 用の音色表と拍子）をまとめる。"""
    rpm = profile.rows_per_measure
    return formats.WriteOptions(
        channel_pans=formats.channel_pans(
            song, plan.channel_pans if plan.channel_plan is not None else profile.channel_pans),
        initial_bpm=plan.bpm,
        instrument_names=song.instrument_names,
        gm_voices=dict(getattr(profile, "gm_voices", {}) or {}),
        rows_per_measure=rpm,
        measure_rows=tuple(
            tuple(s.rows if s.rows is not None else rpm for s in pp.slots for _ in range(s.measures))
            for pp in plan.patterns
        ),
    )


def leveled(profile: GenreProfile, song: Song, plan: SongPlan, fmt: str) -> tuple[Song, formats.WriteOptions]:
    """``fmt`` で書き出す Song と付帯情報に、ジャンルの測定値に基づく音量の底上げを施す（core/level.py）。"""
    opts = write_options(profile, song, plan)
    lv = level.plan_level(song, fmt, PEAK_DB.get(profile.id), opts.channel_pans)
    return level.apply_volume_gain(song, lv.volume_gain), dataclasses.replace(opts, mix_volume=lv.header_volume)


def serialize(profile: GenreProfile, song: Song, plan: SongPlan, fmt: str = formats.DEFAULT_FORMAT, *,
              raw: bool = False) -> bytes:
    """Song を ``fmt`` 形式のバイト列にする（検査はしない）。``raw=True`` なら音量を底上げしない（測定用）。"""
    if raw:
        return formats.get_format(fmt).serialize(song, write_options(profile, song, plan))
    return formats.get_format(fmt).serialize(*leveled(profile, song, plan, fmt))


def generate(
    profile: GenreProfile,
    seed: Optional[int],
    out: Union[str, Path],
    *,
    verify: bool = True,
    tempo: Optional[TempoRequest] = None,
    fmt: str = formats.DEFAULT_FORMAT,
    channels: Optional[int] = None,
) -> Result:
    """Song を生成し、検査して ``fmt`` 形式（既定 mod）のファイルを書き出す。
    検査 ERROR があればファイルを書かない。"""
    output = formats.get_format(fmt)
    if seed is None:
        seed = random.randint(*SEED_RANGE)
    song, plan = compose_song(profile, seed, tempo=tempo, channels=channels)
    physical = effective_channel_plan(profile, plan)
    formats.check_channels(output, len(physical), profile.id)
    data = output.serialize(*leveled(profile, song, plan, fmt))

    issues: list[verify_mod.Issue] = []
    if verify and output.verify is not None:
        issues = output.verify(data, physical)
        for i in issues:
            if i.level == "WARN":
                log.warning("%s %s", i.code, i.message)
            elif i.level == "INFO":
                log.info("%s %s", i.code, i.message)
        errors = [i for i in issues if i.level == "ERROR"]
        if errors:
            raise VerificationError(errors)

    path = Path(out)
    writer.write_file(path, data)
    return Result(seed=seed, path=path, song=song, plan=plan, issues=issues, tempo_request=tempo, fmt=fmt,
                  channels_request=channels)
