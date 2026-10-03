"""テスト用の最小ジャンルと補助。"""
from __future__ import annotations

from mod_weaver.core.model import ChordSpec, GmVoice
from mod_weaver.core.synth_presets import PRESETS
from mod_weaver.framework.context import Generator
from mod_weaver.framework.genre import Genre, Harmony, Instrument, Part, Section


class _Pluck(Generator):
    """各小節の頭に1音。区間で何が起きるかを単純にして、エンジン・登録簿・CLI の検査に使う。"""

    def measure(self, m):
        m.note(0, "a", 24, vel=40)


class DummyGenre(Genre):
    """1区間（4小節）・4/4・MOD 4ch だけの最小ジャンル。"""

    id = "dummy"
    category = "style"
    display_name = "Dummy"
    description = "test"
    description_en = "test"
    title = "Dummy"
    tempo_choices = (100, 110)
    instruments = {"a": Instrument(patch=PRESETS["keys_ep"], gm=GmVoice(program=0))}
    harmony = Harmony(keys=(0,), mode="ionian", progressions=(("p", (ChordSpec(0, "maj"),)),), n_progressions=1)
    sections = {"a": Section()}
    form = ("a",)
    parts = (Part("a", _Pluck()),)
    mod_channels = {4: 1}


def make_genre(**attrs):
    return type("G", (DummyGenre,), attrs)()
