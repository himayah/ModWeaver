"""出力の基準（golden）: 全ジャンル × 全形式（MOD は宣言された全予算、MP3 は除く）× seed 1 の出力の SHA-256。

意図して出力を変えたとき（音色・生成規則・Realizer の変更）は ``python tools/update_golden.py`` で ``golden.json`` を更新し、
そのコミットで理由を書く。**浮動小数点を使う合成なので、別の OS・Python の版では末尾が違う値になることがある**
（その場合は同じ環境で更新するか、``test_golden_covers_every_genre_and_format`` だけを頼りにする）。
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from mod_weaver import engine
from mod_weaver.core import native
from mod_weaver.framework.compose import compose, resolve_plan
from mod_weaver.framework.realize.midi import realize_midi
from mod_weaver.framework.realize.tracker import realize
from mod_weaver.framework.target import resolve

GOLDEN_PATH = Path(__file__).with_name("golden.json")
SEED = 1


def keys_for(genre) -> list[str]:
    return [f"mod:{n}" for n in sorted(genre.mod_channels)] + ["s3m", "xm", "it", "midi"]


def hashes_for(genre) -> dict[str, str]:
    """``genre`` の出力の SHA-256（キーは ``keys_for``）。Score はテンポの機能を揃えるため形式ごとに作る。"""
    out = {}
    for key in keys_for(genre):
        fmt, _, n = key.partition(":")
        target = resolve(fmt, int(n) if n else None, genre, SEED)
        plan = resolve_plan(genre, SEED)
        score = compose(genre, plan, SEED, target.features)
        data = realize_midi(genre, score, plan, target) if fmt == "midi" else native.serialize(
            realize(genre, score, plan, target))
        out[key] = hashlib.sha256(data).hexdigest()
    return out


def all_hashes() -> dict[str, dict[str, str]]:
    return {g.id: hashes_for(g) for g in engine.list_genres()}


def load() -> dict[str, dict[str, str]]:
    return json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))


def save(data: dict[str, dict[str, str]]) -> None:
    GOLDEN_PATH.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n", encoding="utf-8")
