"""F3 の試験移植（pop・racing-breaks・march）の完了条件（FRAMEWORK_REDESIGN.md §16.2 F3）。

- 3ジャンルが MOD の（それぞれの declared）全予算で生成・検査に通る。
- ladder の結果が現行の ``ARRANGEMENTS``（pop・racing-breaks）／固定4ch構成（march）と一致する
  （§15.1「編成の対応表」の簡易版。並びと lane の楽器構成だけを比べ、畳んだ結果の bit 一致は比べない
  ― 乱数の消費順が変わってよい（D9）ため、同じ seed でも打点そのものは一致しない）。
- 聴き比べ用の .mod ファイルを生成する（実際の試聴はユーザーが行う。本テストは生成・検査のみ）。
"""
from __future__ import annotations

import pathlib
import sys

import pytest

GENRES_DIR = pathlib.Path(__file__).parent / "genres"
sys.path.insert(0, str(GENRES_DIR))

from mod_weaver.genres.march import MarchGenre as MarchToy  # noqa: E402
from pop import PopToy  # noqa: E402
from racing_breaks import RacingBreaksToy  # noqa: E402

from mod_weaver.core.formats import get_format  # noqa: E402
from mod_weaver.framework.compose import compose, resolve_plan  # noqa: E402
from mod_weaver.framework.realize import lanes as lanesmod  # noqa: E402
from mod_weaver.core import native  # noqa: E402
from mod_weaver.framework.realize.tracker import realize  # noqa: E402
from mod_weaver.framework.target import resolve as resolve_target  # noqa: E402

FMT = get_format("mod")
SEEDS = (1, 2, 3, 4, 5)

GENRES = {
    "pop": (PopToy(), (4, 6, 8)),
    "racing-breaks": (RacingBreaksToy(), (4, 6, 8)),
    "march": (MarchToy(), (4,)),   # 現行どおり 4ch 専用（§15.4）
}

# 現行 ARRANGEMENTS の編成（チャンネル名の並び。drums は旧 ChannelDef 名、以下は現行 genres/*.py の宣言）
OLD_ARRANGEMENTS = {
    "pop": {
        4: ["drums(single)", "bass", "comp", "lead"],
        6: ["drums(kick/snare)", "drums(hat)", "bass", "comp", "lead", "pad"],
        8: ["drums(kick/snare)", "drums(hat)", "bass", "comp", "lead", "pad", "lead echo", "strings"],
    },
    "racing-breaks": {
        4: ["drums(single)", "bass", "comp", "lead"],
        6: ["drums(kick/snare)", "drums(hat_ride)", "bass", "comp", "lead", "pad"],
        8: ["drums(kick/snare)", "drums(hat_ride)", "bass", "comp", "lead", "pad", "lead echo", "brass"],
    },
    "march": {4: ["drums(single)", "tuba", "harm(single)", "picc"]},
}


def _layout(genre, budget: int):
    plan = resolve_plan(genre, seed=1)
    score = compose(genre, plan, seed=1, features=frozenset())
    return lanesmod.compute_layout(genre, score, budget=budget)


@pytest.mark.parametrize("name", GENRES)
def test_ladder_matches_old_arrangement_channel_count(name: str) -> None:
    """lane の物理チャンネル数が、現行 ``ARRANGEMENTS``（march は固定4ch構成）の編成の数と一致する
    （§15.1「編成の対応表」の簡易版。楽器の組合せそのものは pop/racing-breaks で手動確認済み、
    F3 の実装メモ参照）。"""
    genre, budgets = GENRES[name]
    for b in budgets:
        layout = _layout(genre, b)
        assert len(layout.lanes) == b == len(OLD_ARRANGEMENTS[name][b])


@pytest.mark.parametrize("name", GENRES)
def test_realize_mod_passes_verify_across_declared_budgets(name: str) -> None:
    genre, budgets = GENRES[name]
    for seed in SEEDS:
        plan = resolve_plan(genre, seed=seed)
        score = compose(genre, plan, seed=seed, features=frozenset())
        for b in budgets:
            target = resolve_target("mod", b, genre, seed=seed)
            rs = realize(genre, score, plan, target)
            assert rs.patterns[0].channels == b
            errors = [i for i in native.verify("mod", native.serialize(rs)) if i.level == "ERROR"]
            assert not errors, (name, seed, b, errors)


def test_generate_reference_files_for_listening(tmp_path) -> None:
    """3ジャンルの .mod を書き出す（F3 完了条件の「基準の曲と聴き比べて問題が無い」はユーザーが試聴して
    確認する。このテストは生成・検査が通ることだけを確認する）。"""
    from mod_weaver.core import writer

    out_dir = pathlib.Path("output") / "f3-trial"
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, (genre, budgets) in GENRES.items():
        for b in budgets:
            seed = 42
            plan = resolve_plan(genre, seed=seed)
            score = compose(genre, plan, seed=seed, features=frozenset())
            target = resolve_target("mod", b, genre, seed=seed)
            data = native.serialize(realize(genre, score, plan, target))
            assert not [i for i in native.verify("mod", data) if i.level == "ERROR"]
            path = out_dir / f"{name}.{b}ch.mod"
            writer.write_file(path, data)
            assert path.exists() and path.stat().st_size > 0
