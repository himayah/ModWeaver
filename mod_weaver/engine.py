"""生成エンジン（設計書 §3.2、§6.5、§7）。

エンジンが所有する処理: テンポセル挿入、pattern への転記、順序表、バイト化、検査、書込。
プロファイルが所有する処理: 音色、和声、リズム、フレーズ、パート間の音の配置。
"""
from __future__ import annotations

import logging
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

from .core import verify as verify_mod
from .core import writer
from .core.model import (
    MAX_SAMPLES,
    NUM_CHANNELS,
    ROWS_PER_PATTERN,
    Cell,
    Instrument,
    MeasureBuffer,
    MeasureCtx,
    Pattern,
    PatternCtx,
    RngStreams,
    Song,
    SongPlan,
)
from .errors import ChannelConflictError, PlanError, SampleConstraintError, VerificationError
from .profiles.base import GenreProfile

log = logging.getLogger("mod_weaver")

SEED_RANGE = (100000, 999999)   # seed 省略時の乱数範囲（旧仕様どおり）


@dataclass
class Result:
    seed: int
    path: Optional[Path]
    song: Song
    plan: SongPlan
    issues: list[verify_mod.Issue]


# ------------------------------------------------------------
# 契約検査（§7.3）
# ------------------------------------------------------------

def validate_timebase(rows_per_measure: int) -> None:
    """小節長の制約。現行は「64 の約数」。将来の可変小節拡張（EXT-2）はここを差し替える。"""
    if rows_per_measure <= 0 or ROWS_PER_PATTERN % rows_per_measure != 0:
        raise PlanError(f"rows_per_measure must divide {ROWS_PER_PATTERN}: {rows_per_measure}")


def validate_profile(profile: GenreProfile) -> None:
    validate_timebase(profile.rows_per_measure)
    if len(profile.channel_plan) != NUM_CHANNELS:
        raise PlanError(f"{profile.id}: channel_plan must have {NUM_CHANNELS} roles")
    if profile.tempo_policy not in ("engine", "profile"):
        raise PlanError(f"{profile.id}: invalid tempo_policy {profile.tempo_policy!r}")
    if profile.rng_mode not in ("single", "streams"):
        raise PlanError(f"{profile.id}: invalid rng_mode {profile.rng_mode!r}")
    if profile.target_format not in writer.WRITERS:
        raise PlanError(f"{profile.id}: unsupported target_format {profile.target_format!r}")
    if len(profile.title) > 20 or not profile.title.isascii():
        raise PlanError(f"{profile.id}: title must be ASCII and <= 20 chars: {profile.title!r}")


def validate_plan(profile: GenreProfile, plan: SongPlan) -> None:
    where = f"[{profile.id}]"
    if plan.bpm not in profile.tempo_choices:
        raise PlanError(f"{where} bpm {plan.bpm} not in tempo_choices {profile.tempo_choices}")
    if not plan.patterns:
        raise PlanError(f"{where} plan has no patterns")
    for i, pp in enumerate(plan.patterns):
        total = sum(s.measures for s in pp.slots) * profile.rows_per_measure
        if total != ROWS_PER_PATTERN or any(s.measures < 1 for s in pp.slots):
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


def apply_tempo(song: Song, bpm: int) -> None:
    """``order[0]`` の pattern の row 0 に ``F bpm`` を挿入する（tempo_policy="engine"）。

    ①空きチャンネルのうち最小番号、②なければ note を持つが vol/effect の無いチャンネル
    （サンプル既定音量で鳴る）。いずれも無ければ ChannelConflictError（プロファイルの不具合）。
    """
    pattern = song.patterns[song.order[0]]
    for ch in range(pattern.channels):
        if pattern.get(0, ch).is_empty:
            pattern.replace(0, ch, Cell(None, 0, 0x0F, bpm))
            return
    for ch in range(pattern.channels):
        c = pattern.get(0, ch)
        if c.note is not None and c.vol is None and not c.has_effect:
            pattern.replace(0, ch, Cell(c.note, c.sample, 0x0F, bpm))
            return
    raise ChannelConflictError(
        f"no channel available for tempo command at pattern {song.order[0]} row 0"
    )


def compose_song(profile: GenreProfile, seed: int) -> tuple[Song, SongPlan]:
    """純粋関数（I/O なし）。Song と SongPlan を返す。"""
    validate_profile(profile)
    rng = _make_rng(profile, seed)

    specs, instruments = make_instruments(profile)
    plan = profile.plan(rng)
    validate_plan(profile, plan)
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
        for slot in pp.slots:
            for k in range(slot.measures):
                mctx = MeasureCtx(
                    pattern=pctx,
                    measure_idx=m,
                    n_measures=n_measures,
                    chord=slot.chord,
                    chord_measure_offset=k,
                    is_last=(m == n_measures - 1),
                    instruments=instruments,
                )
                buf = MeasureBuffer(rpm, profile.channel_plan, profile.strict_buffers)
                profile.compose_measure(mctx, state, rng, buf)
                pattern.blit(buf, m * rpm)
                m += 1
        profile.finalize_pattern(pctx, pattern, state, rng)
        patterns.append(pattern)

    song = Song(profile.title, specs, patterns, list(plan.order))
    for post in profile.post_processors:
        post(song, plan)
    if profile.tempo_policy == "engine":
        apply_tempo(song, plan.bpm)
    return song, plan


def build_song(profile: GenreProfile, seed: int) -> Song:
    """純粋関数（I/O なし）。テストは Song／bytes を直接検査できる。"""
    return compose_song(profile, seed)[0]


def generate(
    profile: GenreProfile,
    seed: Optional[int],
    out: Union[str, Path],
    *,
    verify: bool = True,
) -> Result:
    """Song を生成し、検査して .mod を書き出す。検査 ERROR があればファイルを書かない。"""
    if seed is None:
        seed = random.randint(*SEED_RANGE)
    song, plan = compose_song(profile, seed)
    data = writer.WRITERS[profile.target_format](song)

    issues: list[verify_mod.Issue] = []
    if verify:
        issues = verify_mod.VERIFIERS[profile.target_format](data, profile.channel_plan)
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
    return Result(seed=seed, path=path, song=song, plan=plan, issues=issues)
