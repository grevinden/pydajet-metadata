"""Конфигурация пакета из переменных окружения (pydantic-settings)."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class PydaJetSettings(BaseSettings):
    """Настройки кэша и прочие параметры с префиксом PYDAJET_."""

    model_config = SettingsConfigDict(
        env_prefix="PYDAJET_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    cache_enabled: bool = Field(
        default=True,
        description="Включить cashews-кэш для метаданных и отражения схемы.",
    )
    cache_url: str = Field(
        default="mem://?size=10000",
        description="URL бэкенда cashews (mem://, redis:// и т.д.).",
    )
    cache_prefix: str = Field(
        default="",
        description="Префикс ключей cashews (параметр setup prefix).",
    )
    cache_ttl_metadata: int = Field(
        default=3600,
        ge=0,
        description="TTL кэша list_types / list_objects (секунды).",
    )
    cache_ttl_schema: int = Field(
        default=1800,
        ge=0,
        description="TTL кэша reflect_table / get_pk (секунды).",
    )
    cache_ttl_root_guid: int = Field(
        default=300,
        ge=0,
        description="TTL кэша корневого GUID из _Config (секунды).",
    )


@lru_cache(maxsize=1)
def get_settings() -> PydaJetSettings:
    return PydaJetSettings()


def clear_settings_cache() -> None:
    get_settings.cache_clear()
