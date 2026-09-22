"""テスト用の最小プロファイルと補助。"""
from __future__ import annotations

from mod_weaver.core.model import (
    Cell, ChannelRole, ChordDef, ChordSlot, PatternPlan, SampleSpec, SongPlan,
)
from mod_weaver.profiles.base import GenreProfile

DUMMY_CHORD = ChordDef("X", 0, 12, (12, 16, 19), (12, 14, 16, 19), explicit=True)


def tone(n=64, loop=None):
    return bytes((i * 3) % 200 for i in range(n))


class DummyProfile(GenreProfile):
    """4 measure/pattern、1 pattern、engine テンポの最小プロファイル。"""

    id = "dummy"
    display_name = "Dummy"
    description = "test"
    title = "Dummy"
    default_filename = "Dummy.mod"
    tempo_choices = (100, 110)
    rows_per_measure = 16
    tempo_policy = "engine"
    rng_mode = "streams"
    strict_buffers = True
    channel_plan = (
        ChannelRole("a", frozenset({1})),
        ChannelRole("b", frozenset({2})),
        ChannelRole("c", frozenset({1, 2})),
        ChannelRole("d", frozenset({2})),
    )
    n_measures = 4
    bpm = 100
    order = [0]
    row0_cells: dict = {}          # ch -> Cell を row 0 に置く（apply_tempo の検証用）

    def build_samples(self):
        return {"one": SampleSpec("One", tone(), 40), "two": SampleSpec("Two", tone(), 30)}

    def plan(self, rng):
        slots = [ChordSlot(DUMMY_CHORD, 1) for _ in range(self.n_measures)]
        return SongPlan(self.bpm, [PatternPlan("a", slots)], list(self.order), summary=["dummy"])

    def compose_measure(self, mctx, state, rng, buf):
        if mctx.measure_idx == 0:
            for ch, cell in self.row0_cells.items():
                buf.put(0, ch, cell)
        buf.put(4, 1, mctx.instruments["two"].cell(20, vol=30))


def make_profile(**attrs):
    return type("P", (DummyProfile,), attrs)()


def iter_cells(song):
    """(pattern_index, row, ch, cell) を全セルについて列挙する。"""
    for p, pat in enumerate(song.patterns):
        for r in range(pat.rows):
            for c in range(pat.channels):
                yield p, r, c, pat.get(r, c)


def sample_no(song, name_prefix):
    """SampleSpec.name の接頭辞から sample 番号（1 起点）を引く。"""
    for i, s in enumerate(song.samples, start=1):
        if s.name.startswith(name_prefix):
            return i
    raise KeyError(name_prefix)
