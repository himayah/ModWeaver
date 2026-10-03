from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

import pytest

from mod_weaver import engine  # noqa: F401  (ジャンルを discover する)
from mod_weaver.errors import ProfileNotFoundError
from mod_weaver.framework import registry
from mod_weaver.framework.genre import Genre
from tests.helpers import DummyGenre

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def clean_registry():
    saved = (dict(registry.GENRE_REGISTRY), dict(registry._ALIASES))
    yield
    registry.GENRE_REGISTRY.clear(); registry.GENRE_REGISTRY.update(saved[0])
    registry._ALIASES.clear(); registry._ALIASES.update(saved[1])


def test_nostalgic_is_registered():
    p = registry.get_genre("nostalgic")
    assert isinstance(p, Genre) and p.id == "nostalgic"
    assert "nostalgic" in [c.id for c in registry.list_genres()]


def test_unknown_genre_lists_choices():
    with pytest.raises(ProfileNotFoundError, match="choices: .*nostalgic"):
        registry.get_genre("nope")


def test_register_and_alias(clean_registry):
    @registry.register_genre
    class Extra(DummyGenre):
        id = "extra"
        aliases = ("ex", "xtra")

    assert registry.resolve_id("ex") == "extra" == registry.resolve_id("extra")
    assert isinstance(registry.get_genre("xtra"), Extra)
    assert "extra" in [c.id for c in registry.list_genres()]
    with pytest.raises(ProfileNotFoundError, match="ex->extra"):
        registry.get_genre("zzz")


def test_duplicate_id_or_alias_rejected(clean_registry):
    with pytest.raises(ValueError, match="duplicate genre id"):
        @registry.register_genre
        class Dup(DummyGenre):
            id = "nostalgic"

    @registry.register_genre
    class A(DummyGenre):
        id = "aa"
        aliases = ("shared",)

    with pytest.raises(ValueError, match="duplicate genre alias"):
        @registry.register_genre
        class B(DummyGenre):
            id = "bb"
            aliases = ("shared",)

    with pytest.raises(ValueError):
        @registry.register_genre
        class C(DummyGenre):
            id = "shared"


# --- ジャンルモジュールの自動検出（DESIGN.md §5.6） ---

GENRES_PACKAGE = "mod_weaver.genres"
GENRES_DIR = ROOT / "mod_weaver" / "genres"


def test_every_genre_file_registers_exactly_one_genre():
    names = sorted(p.stem for p in GENRES_DIR.glob("*.py") if not p.stem.startswith("_"))
    assert names, "no genre modules found"
    by_module = {}
    for cls in registry.GENRE_REGISTRY.values():
        by_module.setdefault(cls.__module__, []).append(cls.id)
    assert sorted(by_module) == [f"{GENRES_PACKAGE}.{n}" for n in names]
    assert all(len(ids) == 1 for ids in by_module.values()), by_module


def test_framework_dir_has_no_genre_modules():
    """ジャンルモジュールは genres/ だけに置く（framework/ は仕組みと部品のみ）。"""
    assert not any(c.__module__.startswith("mod_weaver.framework.") for c in registry.GENRE_REGISTRY.values())


@pytest.mark.parametrize("code", ["import mod_weaver.engine", "import mod_weaver.genres.nostalgic",
                                  "import mod_weaver.genres.suspense_slow"])
def test_bundled_genres_load_without_warnings(code):
    """ジャンルモジュールを先に直接 import しても（import 途中で discover が走る）誤警告を出さない。"""
    r = subprocess.run([sys.executable, "-c", code + "; from mod_weaver import engine; "
                        "print(len(engine.list_genres()))"],
                       capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0 and r.stderr == ""
    assert int(r.stdout) == len(registry.GENRE_REGISTRY)


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
from mod_weaver.framework.registry import register_genre
from tests.helpers import DummyGenre

@register_genre
class Good(DummyGenre):
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
    assert registry.resolve_id("fake-good") == "fake-good"
    assert "fake-good" in [c.id for c in registry.list_genres()]
    text = warnings_captured.text
    assert "broken" in text and "oops" in text
    assert "helper" in text and "registers no genre" in text
    assert "_private" not in text and "must not be imported" not in text


def test_discover_twice_is_silent(tmp_path, monkeypatch, warnings_captured, clean_registry):
    pkg = _make_package(tmp_path, monkeypatch, "fake_genres_b", {"good.py": GOOD_GENRE})
    registry.discover(pkg)
    registry.discover(pkg)
    assert "fake-good" in registry.GENRE_REGISTRY and warnings_captured.text == ""


# --- 登録時の検査 ---

@pytest.mark.parametrize("attr", ["description", "description_en"])
@pytest.mark.parametrize("desc", ["", "   ", "two\nlines", "cr\rline", None])
def test_description_must_be_single_nonempty_line(clean_registry, attr, desc):
    bad = type("Bad", (DummyGenre,), {"id": "bad-desc", attr: desc})
    with pytest.raises(ValueError, match=f"{attr} must be"):
        registry.register_genre(bad)


@pytest.mark.parametrize("pid,aliases", [("random", ()), ("r", ()), ("ok-id", ("r",)), ("ok-id2", ("random",))])
def test_reserved_names_rejected(clean_registry, pid, aliases):
    bad = type("Bad", (DummyGenre,), {"id": pid, "aliases": aliases})
    with pytest.raises(ValueError, match="reserved"):
        registry.register_genre(bad)
    assert pid not in registry.GENRE_REGISTRY


def test_empty_id_rejected(clean_registry):
    with pytest.raises(ValueError, match="id"):
        @registry.register_genre
        class Bad(DummyGenre):
            id = ""


@pytest.mark.parametrize("category", [None, "", "misc", "Mood"])
def test_unknown_category_rejected(clean_registry, category):
    bad = type("Bad", (DummyGenre,), {"id": "bad-cat", "category": category})
    with pytest.raises(ValueError, match="category"):
        registry.register_genre(bad)


def test_every_genre_has_a_known_category():
    assert {p.category for p in registry.list_genres()} <= set(registry.CATEGORIES)


def test_categories_of_the_individually_implemented_genres():
    """§6: nostalgic・suspense-* は style、他の個別実装の9ジャンルは genre（一覧の区分に出る）。"""
    cats = {c.id: c.category for c in registry.list_genres()}
    assert {cats[g] for g in ("nostalgic", "suspense-slow", "suspense-chase")} == {"style"}
    assert {cats[g] for g in ("march", "swing-jazz", "prog-rock", "trap", "future-bass", "maqam", "free-jazz",
                              "minimalism", "orchestral")} == {"genre"}
