from __future__ import annotations

import pytest

from mod_weaver import profiles
from mod_weaver.errors import ProfileNotFoundError
from mod_weaver.profiles import registry
from mod_weaver.profiles.base import GenreProfile
from tests.helpers import DummyProfile


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
