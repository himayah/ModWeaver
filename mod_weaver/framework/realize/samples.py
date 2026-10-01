"""楽器のサンプル計画と描画（FRAMEWORK_REDESIGN.md §8.4）。

MOD の sample 番号（1..31）は lane とは独立に決まる: kit/chord_voice/mono の lane に乗る楽器は
1つにつき1サンプル（lane が「まとめ」られていても、鳴らす楽器ごとに別サンプルが要る）。
chord_baked の lane は、実際に使われた和音の形（``NoteEvent.chord``）ごとに別サンプルが要る。
"""
from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

from ...core import synth
from ...core.model import SampleSpec
from ...errors import PlanError
from .lanes import LaneLayout, chord_shapes_of

if TYPE_CHECKING:
    from ...framework.genre import Genre
    from ...framework.score import Score
    from ..target import Target

SampleKey = tuple[str, tuple[int, ...]]   # (楽器名, 和音の形。空なら素の楽器)


def _render_params(target: "Target") -> tuple[float, int]:
    """``target.sample`` から ``synth.render()`` に渡す (oversample, bits)。

    F3 時点では MOD（``target_rate == 0``）だけが実際に通る。S3M/XM/IT 用の
    ``target_rate / 基準レート`` の換算は F4 で実装する（§8.2）。
    """
    caps = target.sample
    if caps is None or caps.target_rate <= 0:
        return 1.0, (caps.bits if caps is not None else 8)
    raise NotImplementedError("oversample ratio for tracker formats other than MOD is implemented in F4")


def _sample_label(inst_name: str, shape: tuple[int, ...]) -> str:
    label = inst_name if not shape else f"{inst_name}_{'.'.join(str(s) for s in shape)}"
    ascii_label = label.encode("ascii", "replace").decode("ascii")
    return ascii_label[:22]


def plan_samples(genre: "Genre", layout: LaneLayout, score: "Score", target: "Target"
                  ) -> tuple[list[SampleSpec], dict[SampleKey, int], tuple[str, ...]]:
    """``Song.samples``（sample 番号順）と ``(楽器名, 和音の形) -> sample 番号`` の対応表、
    ``WriteOptions.instrument_names`` を作る。"""
    oversample, bits = _render_params(target)

    order: list[SampleKey] = []
    seen: set[SampleKey] = set()

    def add(key: SampleKey) -> None:
        if key not in seen:
            seen.add(key)
            order.append(key)

    plain_insts: set[str] = set()
    for lane in layout.lanes:
        if lane.role in ("kit", "chord_voice", "mono"):
            plain_insts.update(lane.insts)
    for name in genre.instruments:              # 宣言順にして出力を決定的にする
        if name in plain_insts:
            add((name, ()))

    by_name = {p.name: p for p in genre.parts}
    for lane in layout.lanes:
        if lane.role == "chord_baked" and lane.insts:
            part = by_name[lane.part_name]
            for shape in sorted(chord_shapes_of(part, score)):
                add((lane.insts[0], shape))

    if len(order) > target.sample.max_samples:
        raise PlanError(f"{genre.id}: needs {len(order)} samples but {target.format} allows only "
                         f"{target.sample.max_samples}")

    specs: list[SampleSpec] = []
    slot_of: dict[SampleKey, int] = {}
    names: list[str] = []
    for i, key in enumerate(order):
        inst_name, shape = key
        inst = genre.instruments[inst_name]
        patch = inst.patch if not shape else synth.chord_patch(inst.patch, shape)
        spec = synth.render(patch, oversample=oversample, bits=bits)
        spec = dataclasses.replace(
            spec,
            name=_sample_label(inst_name, shape),
            volume=inst.volume if inst.volume is not None else spec.volume,
            pan=inst.pan if inst.pan is not None else spec.pan,
        )
        spec.validate()
        specs.append(spec)
        slot_of[key] = i + 1
        names.append(inst_name)
    return specs, slot_of, tuple(names)
