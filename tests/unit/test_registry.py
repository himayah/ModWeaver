from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

import pytest

from mod_weaver import profiles
from mod_weaver.errors import ProfileNotFoundError
from mod_weaver.profiles import registry
from mod_weaver.profiles.base import GenreProfile
from tests.helpers import DummyProfile

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def clean_registry():
    saved = (dict(registry.PROFILE_REGISTRY), dict(registry._ALIASES))
    yield
    registry.PROFILE_REGISTRY.clear(); registry.PROFILE_REGISTRY.update(saved[0])
    registry._ALIASES.clear(); registry._ALIASES.update(saved[1])


def test_nostalgic_is_registered():
    p = profiles.get_profile("nostalgic")
    assert isinstance(p, GenreProfile) and p.id == "nostalgic"
    assert "nostalgic" in [c.id for c in profiles.list_profiles()]


def test_unknown_genre_lists_choices():
    with pytest.raises(ProfileNotFoundError, match="choices: .*nostalgic"):
        profiles.get_profile("nope")


def test_register_and_alias(clean_registry):
    @profiles.register_profile
    class Extra(DummyProfile):
        id = "extra"
        aliases = ("ex", "xtra")

    assert profiles.resolve_id("ex") == "extra" == profiles.resolve_id("extra")
    assert isinstance(profiles.get_profile("xtra"), Extra)
    assert "extra" in [c.id for c in profiles.list_profiles()]
    with pytest.raises(ProfileNotFoundError, match="ex->extra"):
        profiles.get_profile("zzz")


def test_duplicate_id_or_alias_rejected(clean_registry):
    with pytest.raises(ValueError, match="duplicate profile id"):
        @profiles.register_profile
        class Dup(DummyProfile):
            id = "nostalgic"

    @profiles.register_profile
    class A(DummyProfile):
        id = "aa"
        aliases = ("shared",)

    with pytest.raises(ValueError, match="duplicate profile alias"):
        @profiles.register_profile
        class B(DummyProfile):
            id = "bb"
            aliases = ("shared",)

    with pytest.raises(ValueError):
        @profiles.register_profile
        class C(DummyProfile):
            id = "shared"


# --- ジャンルモジュールの自動検出（DESIGN.md §5.6） ---

GENRES_DIR = Path(registry.__file__).resolve().parents[1] / "genres"


def test_every_genre_file_registers_exactly_one_genre():
    names = sorted(p.stem for p in GENRES_DIR.glob("*.py") if not p.stem.startswith("_"))
    assert names, "no genre modules found"
    by_module = {}
    for cls in registry.PROFILE_REGISTRY.values():
        by_module.setdefault(cls.__module__, []).append(cls.id)
    assert sorted(by_module) == [f"{registry.GENRES_PACKAGE}.{n}" for n in names]
    assert all(len(ids) == 1 for ids in by_module.values()), by_module


def test_profiles_dir_has_no_genre_modules():
    """ジャンルモジュールは genres/ だけに置く（profiles/ は仕組みと補助のみ）。"""
    assert not any(c.__module__.startswith("mod_weaver.profiles.") for c in registry.PROFILE_REGISTRY.values())


@pytest.mark.parametrize("code", ["import mod_weaver.profiles", "import mod_weaver.genres.nostalgic",
                                  "import mod_weaver.genres.suspense_slow"])
def test_bundled_genres_load_without_warnings(code):
    """ジャンルモジュールを先に直接 import しても（import 途中で discover が走る）誤警告を出さない。"""
    r = subprocess.run([sys.executable, "-c", code + "; from mod_weaver import profiles; "
                        "print(len(profiles.list_profiles()))"],
                       capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0 and r.stderr == ""
    assert int(r.stdout) == len(registry.PROFILE_REGISTRY)


def _make_package(tmp_path, monkeypatch, name, files):
    pkg = tmp_path / name
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    for fname, body in files.items():
        (pkg / fname).write_text(body, encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    for mod in [m for m in sys.modules if m == name or m.startswith(name + ".")]:
        monkeypatch.delitem(sys.modules, mod)
    return name


@pytest.fixture
def warnings_captured(monkeypatch, caplog):
    """cli.main が mod_weaver ロガーを propagate=False・独自ハンドラにするため、実行順に依存しないよう戻す。"""
    log = logging.getLogger("mod_weaver")
    monkeypatch.setattr(log, "propagate", True)
    monkeypatch.setattr(log, "handlers", [])
    with caplog.at_level(logging.WARNING, logger="mod_weaver"):
        yield caplog


GOOD_GENRE = """
from mod_weaver.profiles import register_profile
from tests.helpers import DummyProfile

@register_profile
class Good(DummyProfile):
    id = "fake-good"
    description = "足すだけで一覧に出るジャンル"
"""


def test_discover_registers_dropped_in_module_and_skips_bad_ones(tmp_path, monkeypatch, warnings_captured,
                                                                 clean_registry):
    pkg = _make_package(tmp_path, monkeypatch, "fake_genres_a", {
        "good.py": GOOD_GENRE,
        "helper.py": "X = 1\n",
        "broken.py": "raise RuntimeError('oops')\n",
        "_private.py": "raise RuntimeError('must not be imported')\n",
    })
    registry.discover(pkg)
    assert profiles.resolve_id("fake-good") == "fake-good"
    assert "fake-good" in [c.id for c in profiles.list_profiles()]
    text = warnings_captured.text
    assert "broken" in text and "oops" in text
    assert "helper" in text and "registers no genre" in text
    assert "_private" not in text and "must not be imported" not in text


def test_discover_twice_is_silent(tmp_path, monkeypatch, warnings_captured, clean_registry):
    pkg = _make_package(tmp_path, monkeypatch, "fake_genres_b", {"good.py": GOOD_GENRE})
    registry.discover(pkg)
    registry.discover(pkg)
    assert "fake-good" in registry.PROFILE_REGISTRY and warnings_captured.text == ""


# --- 登録時の検査 ---

@pytest.mark.parametrize("attr", ["description", "description_en"])
@pytest.mark.parametrize("desc", ["", "   ", "two\nlines", "cr\rline", None])
def test_description_must_be_single_nonempty_line(clean_registry, attr, desc):
    bad = type("Bad", (DummyProfile,), {"id": "bad-desc", attr: desc})
    with pytest.raises(ValueError, match=f"{attr} must be"):
        profiles.register_profile(bad)


@pytest.mark.parametrize("pid,aliases", [("random", ()), ("r", ()), ("ok-id", ("r",)), ("ok-id2", ("random",))])
def test_reserved_names_rejected(clean_registry, pid, aliases):
    bad = type("Bad", (DummyProfile,), {"id": pid, "aliases": aliases})
    with pytest.raises(ValueError, match="reserved"):
        profiles.register_profile(bad)
    assert pid not in registry.PROFILE_REGISTRY


def test_empty_id_rejected(clean_registry):
    with pytest.raises(ValueError, match="id"):
        @profiles.register_profile
        class Bad(DummyProfile):
            id = ""


@pytest.mark.parametrize("category", [None, "", "misc", "Mood"])
def test_unknown_category_rejected(clean_registry, category):
    bad = type("Bad", (DummyProfile,), {"id": "bad-cat", "category": category})
    with pytest.raises(ValueError, match="category"):
        profiles.register_profile(bad)


def test_every_genre_has_a_known_category():
    assert {p.category for p in profiles.list_profiles()} <= set(registry.CATEGORIES)
