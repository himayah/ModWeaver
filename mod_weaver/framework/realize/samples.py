"""楽器のサンプル計画と描画（DESIGN.md §4.9）。

サンプル番号は lane とは独立に決まる: kit/chord_voice/mono の lane に乗る楽器は1つにつき1サンプル
（lane が「まとめ」られていても、鳴らす楽器ごとに別サンプルが要る）。chord_baked の lane は、実際に
使われた和音の形（``NoteEvent.chord``）ごとに別サンプルが要る。

``SampleKey = (楽器名, 和音の形, セント, パン)``:
- セント: 書かれた音高の小数部と ``Instrument.tune_cents`` から作る変種。MOD 以外は再生レートに
  ``2^(cents/1200)`` を掛け（整数セント）、MOD は MOD の finetune（1 単位 12.5 セント、-8..7）を変えた同じ波形の
  サンプルにする（鍵の3つ目は finetune の単位。音高は整数の tracker note に丸める）。
- パン: XM だけ。XM は発音のたびにサンプルのパンへ戻るので、lane のパンごとに別のサンプルにする。
"""
from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Optional

from ...core import dsp, synth
from ...core.model import SampleSpec
from ...core.pitch import PERIODS
from ...errors import PlanError, SampleConstraintError
from .lanes import Lane, LaneLayout, Placement
from .voice import VoiceSlot

if TYPE_CHECKING:
    from ...framework.genre import Genre
    from ...framework.score import Score
    from ..target import Target

# MOD の finetune の1単位（実プレイヤー libopenmpt で測定: -8 で -100、+7 で +87 セント＝12.5 セント刻み）。
# （旧い実装は 7.8125 セントとしていたが誤りで、旧パイプラインの微分音はこのためずれていた。その定数は F8 で消した）
MOD_FINETUNE_CENTS = 12.5

SampleKey = tuple[str, tuple[int, ...], int, Optional[int]]   # (楽器名, 和音の形, セント, パン)


def sample_key(fmt: str, genre: "Genre", p: Placement, lane: Lane, voice=None):
    """発音 ``p``（lane ``lane`` 上）が使うサンプルの鍵。計画（``plan_samples``）と書き込み（tracker）が共用する。
    歌声の音符（``p.syl``）は ``VoiceSlot``（``SampleKey`` とは別の型）を返す。"""
    if p.syl is not None:
        return voice.slot_for(p, lane.pan if fmt == "xm" else None)
    cents = 0
    inst = genre.instruments[p.inst]
    if inst.is_pitched and p.pitch is not None:
        residual = (p.pitch - round(p.pitch)) * 100 + inst.tune_cents
        cents = max(-8, min(7, round(residual / MOD_FINETUNE_CENTS))) if fmt == "mod" else round(residual)
    pan = lane.pan if fmt == "xm" else None
    return (p.inst, p.chord if p.chord else (), cents, pan)


def render_for(patch: synth.Patch, target: "Target") -> SampleSpec:
    """``target`` に合わせて描画する（DESIGN.md §4.8）。倍率 m ＝ 目標レート / 実際の再生レート。1サンプルの
    上限（S3M の 64000 byte など）を超えるときは m を下げ、m=1 でも超えるなら ``SampleConstraintError``。"""
    caps = target.sample
    if caps.target_rate <= 0:
        return synth.render(patch, oversample=1.0, bits=caps.bits)
    real_rate = dsp.CLOCK / PERIODS[patch.rate_note]
    m = max(1.0, caps.target_rate / real_rate)
    spec = synth.render(patch, oversample=m, bits=caps.bits)
    for _ in range(4):
        if len(spec.data) <= caps.max_bytes or m <= 1.0:
            break
        m = max(1.0, m * caps.max_bytes / len(spec.data) * 0.97)
        spec = synth.render(patch, oversample=m, bits=caps.bits)
    if len(spec.data) > caps.max_bytes:
        raise SampleConstraintError(f"{patch.name}: {len(spec.data)} bytes exceeds {caps.max_bytes} "
                                     f"({target.format}) even at oversample 1.0")
    return spec


def _sample_label(inst_name: str, shape: tuple[int, ...], cents: int = 0, pan: Optional[int] = None,
                  unit: str = "c") -> str:
    label = inst_name if not shape else f"{inst_name}_{'.'.join(str(s) for s in shape)}"
    if cents:
        label += f"{cents:+d}{unit}"
    if pan is not None:
        label += f"@{pan}"
    return label.encode("ascii", "replace").decode("ascii")[:22]


def plan_samples(genre: "Genre", layout: LaneLayout, score: "Score", target: "Target",
                  placements_by_section: dict, voice=None) -> tuple[list[SampleSpec], dict[SampleKey, int],
                                                                    tuple[str, ...], tuple[Optional[float], ...]]:
    """``(samples, slot_of, instrument_names, release)`` を返す。``slot_of`` は鍵 → sample 番号（1 始まり）。
    ``release`` は sample 番号順の ``Instrument.release_s``。"""
    fmt = target.format
    lane_by_index = {l.index: l for l in layout.lanes}

    used: set[SampleKey] = set()
    for placements, _autos in placements_by_section.values():
        for p in placements:
            if p.kind == "note":
                used.add(sample_key(fmt, genre, p, lane_by_index[p.lane], voice))

    decl_index = {name: i for i, name in enumerate(genre.instruments)}
    voice_keys = sorted((k for k in used if isinstance(k, VoiceSlot)),
                        key=lambda k: (decl_index[k.inst], k.syl, k.bucket, k.pan or 0))
    used = {k for k in used if not isinstance(k, VoiceSlot)}
    plain = sorted((k for k in used if not k[1]), key=lambda k: (decl_index[k[0]], k[2], k[3] or 0))
    baked_keys = [k for k in used if k[1]]
    baked = sorted(baked_keys, key=lambda k: (decl_index[k[0]], k[1], k[2], k[3] or 0))
    order = plain + baked + voice_keys

    if len(order) > target.sample.max_samples:
        raise PlanError(f"{genre.id}: needs {len(order)} samples but {target.format} allows only "
                         f"{target.sample.max_samples}")

    specs: list[SampleSpec] = []
    slot_of: dict[SampleKey, int] = {}
    names: list[str] = []
    release: list[Optional[float]] = []
    for i, key in enumerate(order):
        if isinstance(key, VoiceSlot):
            spec = voice.sample(key, genre.instruments[key.inst])
            spec.validate()
            specs.append(spec)
            slot_of[key] = i + 1
            names.append(key.inst)
            release.append(genre.instruments[key.inst].release_s)
            continue
        inst_name, shape, cents, pan = key
        inst = genre.instruments[inst_name]
        patch = inst.patch if not shape else synth.chord_patch(inst.patch, shape)
        spec = render_for(patch, target)
        changes: dict = dict(
            name=_sample_label(inst_name, shape, cents, pan, "f" if fmt == "mod" else "c"),
            volume=inst.volume if inst.volume is not None else spec.volume,
            pitched=inst.is_pitched,        # Instrument.pitched の上書きを反映する（None は patch のまま）
        )
        if fmt == "mod":
            changes["pan"] = inst.pan if inst.pan is not None else spec.pan
            if cents:
                changes["finetune"] = max(-8, min(7, spec.finetune + cents))
        else:
            changes["pan"] = pan if pan is not None else 128
            if cents and spec.rate_hz is not None:
                changes["rate_hz"] = spec.rate_hz * 2 ** (cents / 1200)
        spec = dataclasses.replace(spec, **changes)
        spec.validate()
        specs.append(spec)
        slot_of[key] = i + 1
        names.append(inst_name)
        release.append(inst.release_s)
    return specs, slot_of, tuple(names), tuple(release)
