"""Интеграция cashews для синхронного кода pydajet / pydajet_metadata."""

from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Callable
from typing import TypeVar, cast

from cashews import NOT_NONE, cache

from pydajet_metadata.settings import get_settings

T = TypeVar("T")

_setup_done = False


def cache_scope_key(connection_string: str, data_source: str) -> str:
    payload = f"{data_source.lower()}\0{connection_string}".encode()
    return hashlib.sha256(payload).hexdigest()[:32]


def metadata_tag(scope: str) -> str:
    return f"metadata:{scope}"


def schema_tag(scope: str) -> str:
    return f"schema:{scope}"


def ensure_cache_setup() -> None:
    global _setup_done
    if _setup_done:
        return
    settings = get_settings()
    cache.setup(
        settings.cache_url,
        prefix=settings.cache_prefix,
        enable=settings.cache_enabled,
    )
    _setup_done = True


def reset_cache_setup() -> None:
    """Сброс инициализации (тесты)."""
    global _setup_done
    _setup_done = False


def _run_async(coro: object) -> object:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)  # type: ignore[arg-type]
    raise RuntimeError(
        "pydajet_metadata cache cannot run inside a running event loop; "
        "use async APIs or disable PYDAJET_CACHE_ENABLED."
    )


async def _cache_get_or_set_async(
    key: str,
    ttl: int,
    tags: tuple[str, ...],
    factory: Callable[[], T],
) -> T:
    ensure_cache_setup()
    await cache.init()
    cached = await cache.get(key, default=NOT_NONE)
    if cached is not NOT_NONE:
        return cast(T, cached)
    value = factory()
    if ttl > 0:
        await cache.set(key, value, expire=ttl, tags=tags)
    return value


def cache_get_or_set(
    *,
    scope: str,
    category: str,
    suffix: str,
    ttl: int,
    tags: tuple[str, ...],
    factory: Callable[[], T],
) -> T:
    settings = get_settings()
    if not settings.cache_enabled:
        return factory()
    key = f"{category}:{scope}:{suffix}"
    return cast(T, _run_async(_cache_get_or_set_async(key, ttl, tags, factory)))


async def _invalidate_scope_async(scope: str) -> None:
    ensure_cache_setup()
    await cache.init()
    await cache.delete_tags(metadata_tag(scope))
    await cache.delete_tags(schema_tag(scope))


def invalidate_cache_scope(scope: str) -> None:
    if not scope or not get_settings().cache_enabled:
        return
    _run_async(_invalidate_scope_async(scope))
