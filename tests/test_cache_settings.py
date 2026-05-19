"""Настройки кэша и cashews."""

from __future__ import annotations

import os

import pytest

from pydajet_metadata._cache import (
    cache_get_or_set,
    cache_scope_key,
    invalidate_cache_scope,
    metadata_tag,
    reset_cache_setup,
)
from pydajet_metadata.settings import PydaJetSettings, clear_settings_cache, get_settings


@pytest.fixture(autouse=True)
def _reset_cache_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PYDAJET_CACHE_ENABLED", "true")
    clear_settings_cache()
    reset_cache_setup()
    yield
    clear_settings_cache()
    reset_cache_setup()


def test_settings_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PYDAJET_CACHE_TTL_METADATA", "120")
    clear_settings_cache()
    settings = get_settings()
    assert settings.cache_ttl_metadata == 120


def test_cache_scope_stable() -> None:
    a = cache_scope_key("Host=1", "postgresql")
    b = cache_scope_key("Host=1", "postgresql")
    c = cache_scope_key("Host=2", "postgresql")
    assert a == b
    assert a != c


def test_cache_get_or_set_hits_backend() -> None:
    calls = 0

    def factory() -> int:
        nonlocal calls
        calls += 1
        return 42

    scope = cache_scope_key("test", "postgresql")
    first = cache_get_or_set(
        scope=scope,
        category="metadata",
        suffix="unit",
        ttl=60,
        tags=(metadata_tag(scope),),
        factory=factory,
    )
    second = cache_get_or_set(
        scope=scope,
        category="metadata",
        suffix="unit",
        ttl=60,
        tags=(metadata_tag(scope),),
        factory=factory,
    )
    assert first == 42 == second
    assert calls == 1


def test_invalidate_cache_scope() -> None:
    calls = 0

    def factory() -> str:
        nonlocal calls
        calls += 1
        return "v"

    scope = cache_scope_key("inv", "postgresql")
    tags = (metadata_tag(scope),)
    cache_get_or_set(
        scope=scope,
        category="metadata",
        suffix="x",
        ttl=3600,
        tags=tags,
        factory=factory,
    )
    invalidate_cache_scope(scope)
    cache_get_or_set(
        scope=scope,
        category="metadata",
        suffix="x",
        ttl=3600,
        tags=tags,
        factory=factory,
    )
    assert calls == 2


def test_cache_disabled_skips_store(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PYDAJET_CACHE_ENABLED", "false")
    clear_settings_cache()
    reset_cache_setup()
    calls = 0

    def factory() -> int:
        nonlocal calls
        calls += 1
        return 1

    scope = cache_scope_key("off", "postgresql")
    cache_get_or_set(
        scope=scope,
        category="metadata",
        suffix="y",
        ttl=60,
        tags=(metadata_tag(scope),),
        factory=factory,
    )
    cache_get_or_set(
        scope=scope,
        category="metadata",
        suffix="y",
        ttl=60,
        tags=(metadata_tag(scope),),
        factory=factory,
    )
    assert calls == 2
    assert get_settings().cache_enabled is False
