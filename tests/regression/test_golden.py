"""出力の基準（golden.json）との一致。意図して出力を変えたときは ``python tools/update_golden.py``。"""
from __future__ import annotations

import pytest

from mod_weaver import engine
from tests.regression import golden_lib

GOLDEN = golden_lib.load()
IDS = [g.id for g in engine.list_genres()]


def test_golden_covers_every_genre_and_format():
    assert sorted(GOLDEN) == sorted(IDS)
    for g in engine.list_genres():
        assert sorted(GOLDEN[g.id]) == sorted(golden_lib.keys_for(g)), g.id


@pytest.mark.parametrize("genre", IDS)
def test_output_matches_the_golden_hashes(genre):
    got = golden_lib.hashes_for(engine.get_genre(genre))
    changed = sorted(k for k in got if got[k] != GOLDEN[genre].get(k))
    assert not changed, (f"{genre}: output changed for {changed}. If this is intended, run "
                         f"`python tools/update_golden.py {genre}` and say why in the commit message.")
