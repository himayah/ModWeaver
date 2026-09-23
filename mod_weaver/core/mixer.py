"""パート間リアクティブ・ミキサー（CORE_EXTENSION_DESIGN §4.4、EXT-4）。

- ``SidechainRule``/``apply_sidechain``: あるサンプル（``trigger_sample`）が鳴った row を検出し、
  別チャンネルの音量を一時的にダッキングして線形復帰させる後処理（``profile.post_processors`` から
  適用する）。``vol`` フィールドのみを操作し、既存の非vol effectセルには一切手を出さない。
- ``sample_offset_param``: ``9xx``（Sample Offset）の param を計算する純粋関数。長尺サンプルの
  特定位置（ブレイクビーツのスライス、ヴォーカルチョップのシラブル等）を叩き分けるのに使う。
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Optional, Sequence

from ..errors import SampleConstraintError
from .composer import ramp
from .model import Cell, Pattern, Song


@dataclass(frozen=True)
class SidechainRule:
    trigger_sample: int        # build_samples() 挿入順で決まるサンプル番号（プロファイルの定数）
    target_channel: int        # ducking 対象のチャンネル index（0始まり）
    duck_ratio: float = 0.3    # 元音量に対する比率（0..1）
    release_rows: int = 2      # トリガ後、元の音量へ線形復帰させる row 数

    def __post_init__(self) -> None:
        if not 1 <= self.trigger_sample <= 31:
            raise SampleConstraintError(f"trigger_sample out of range: {self.trigger_sample}")
        if not 0.0 <= self.duck_ratio <= 1.0:
            raise SampleConstraintError(f"duck_ratio out of range: {self.duck_ratio}")
        if self.release_rows < 0:
            raise SampleConstraintError(f"release_rows must be >= 0: {self.release_rows}")


def apply_sidechain(song: Song, rules: Sequence[SidechainRule]) -> None:
    """``song`` の全 pattern に、``rules`` のサイドチェイン・ダッキングを適用する。"""
    for pattern in song.patterns:
        for rule in rules:
            _duck_pattern(pattern, rule)


def _trigger_rows(pattern: Pattern, trigger_sample: int) -> list[int]:
    return [
        r for r in range(pattern.rows)
        if any(pattern.get(r, c).sample == trigger_sample and pattern.get(r, c).note is not None
               for c in range(pattern.channels))
    ]


def _running_volume(pattern: Pattern, ch: int, upto_row: int, fallback: Optional[int]) -> Optional[int]:
    """target channel の ``upto_row`` 直前までを走査し、直近の実効音量を求める（``verify._check_volume_sum``
    と同じ後方追跡）。note+sample のみ（vol/effect なし）のセルはサンプル既定音量＝不明のため None（安全側でスキップ）。
    """
    vol = fallback
    for r in range(upto_row):
        cell = pattern.get(r, ch)
        if cell.vol is not None:
            vol = cell.vol
        elif cell.note is not None and cell.sample and not cell.has_effect:
            vol = None
    return vol


def _duck_pattern(pattern: Pattern, rule: SidechainRule) -> None:
    ch = rule.target_channel
    triggers = _trigger_rows(pattern, rule.trigger_sample)
    vol: Optional[int] = None
    for i, t_row in enumerate(triggers):
        vol = _running_volume(pattern, ch, t_row, vol)
        if vol is None:
            continue   # このトリガ直前の音量が不明 → 安全側で ducking をスキップ
        base_vol = vol
        _set_vol_preserving_effect(pattern, ch, t_row, round(base_vol * rule.duck_ratio))
        vol = round(base_vol * rule.duck_ratio)
        next_trigger = triggers[i + 1] if i + 1 < len(triggers) else pattern.rows
        release_end = min(t_row + rule.release_rows, next_trigger - 1, pattern.rows - 1)
        n = release_end - t_row
        for k in range(1, n + 1):
            r = t_row + k
            v = ramp(vol, base_vol, k, n + 1)     # composer.ramp を再利用
            if not _set_vol_preserving_effect(pattern, ch, r, v):
                break   # 既存の非vol effectセルに当たったら release を打ち切る（それを壊さない）
            vol = v


def _set_vol_preserving_effect(pattern: Pattern, ch: int, row: int, v: int) -> bool:
    """row の既存セルが note を持てば vol だけ差し替え、空セルなら vol-only セルを新設する。
    既に（vol以外の）effect を持つセルには手を出さない（False を返す）。"""
    cell = pattern.get(row, ch)
    if cell.is_empty:
        pattern.replace(row, ch, Cell(vol=max(0, min(64, v))))
        return True
    if cell.vol is not None or (cell.note is not None and not cell.has_effect):
        pattern.replace(row, ch, dataclasses.replace(cell, vol=max(0, min(64, v)), effect=0, param=0))
        return True
    return False


def sample_offset_param(offset_samples: int, length_words: int) -> int:
    """``9xx`` の param（オフセット = param*256サンプル）。``offset_samples`` に最も近い256の倍数を
    0..255 にクランプして返す（長尺ブレイクビーツ／ヴォーカルチョップの特定位置を叩くため）。
    """
    if offset_samples < 0:
        raise SampleConstraintError(f"offset_samples must be >= 0: {offset_samples}")
    if offset_samples > length_words * 2:
        raise SampleConstraintError(
            f"offset_samples {offset_samples} exceeds sample length ({length_words * 2} samples)"
        )
    param = round(offset_samples / 256.0)
    if param > 255:
        raise SampleConstraintError(
            f"offset {offset_samples} needs param {param} > 255 (sample too short for this offset)"
        )
    return param
