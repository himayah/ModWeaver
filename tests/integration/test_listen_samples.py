"""試聴用の曲の一覧（listen_samples.py。DESIGN.md §11）がジャンルの宣言とずれていないこと。"""
from __future__ import annotations

import listen_samples as L
from mod_weaver.engine import channel_choices, get_genre, list_genres


def test_song_list_is_fixed_and_uses_registered_genres():
    songs = L.songs()
    assert len(songs) == 423 and len(set(songs)) == 423
    ids = {p.id for p in list_genres()}
    assert {g for _, g, _, _ in songs} <= ids
    assert [folder for folder, _, _ in L.ITEMS] == sorted(folder for folder, _, _ in L.ITEMS)


def test_arrangements_cover_every_channel_count_each_genre_can_choose():
    for genre, chs in L.ARRANGEMENTS.items():
        assert chs == channel_choices(get_genre(genre)), genre
    choosers = {p.id for p in list_genres() if len(channel_choices(p)) > 1 and p.id in L.STAGE3}
    assert set(L.ARRANGEMENTS) == choosers
