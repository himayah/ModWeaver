"""動作・音質を確認済みの ``synth.Patch`` 値を集めた参照ライブラリ（DESIGN.md §4.5）。

ここに集めるのは「型としての分類」ではなく「検索・流用のための参照データ」であり、
``core/synth.py`` の型システムには一切影響しない。新しい音色が欲しいときは、
``find()`` で近い説明のプリセットを探し ``dataclasses.replace(既存Patch, ...)`` で
差分だけ変えて ``synth.render()`` → 試聴し、良ければ ``register()`` で追加する
（ゼロから ``Patch`` を組み立てない）。

モジュール構成: ``genre_kits``（既存12ジャンルの音色。ジャンル名で命名）と、楽器の種類ごとの
``drums``・``perc``・``bass``・``keys``・``guitar``・``synths``・``pads``・``orch``・``fx``・``metal``
（第３段階以降の共有音色。楽器名で命名し複数ジャンルで使い回す）。どのモジュールの定数も
``synth_presets.<定数名>`` で参照できる。
"""
from __future__ import annotations

from ._registry import DESCRIPTIONS, PRESETS, find, register  # noqa: F401
from .genre_kits import *  # noqa: F401,F403
from .drums import *  # noqa: F401,F403
from .perc import *  # noqa: F401,F403
from .bass import *  # noqa: F401,F403
from .keys import *  # noqa: F401,F403
from .guitar import *  # noqa: F401,F403
from .synths import *  # noqa: F401,F403
from .pads import *  # noqa: F401,F403
from .orch import *  # noqa: F401,F403
from .fx import *  # noqa: F401,F403
from .metal import *  # noqa: F401,F403
