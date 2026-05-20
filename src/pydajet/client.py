"""Низкоуровневый клиент для чтения метаданных 1С через DaJet Metadata."""

from __future__ import annotations

import logging
from collections.abc import Iterable, Sized
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from System import Guid as _NetGuidClass
    from System.Collections.Generic import List as _NetListClass

from pydajet import DataSourceType, Guid, List
from pydajet._dotnet import (
    DotNetConfiguration,
    DotNetEntity,
    DotNetGuidList,
    DotNetMetadataIndex,
    DotNetMetadataProvider,
    DotNetMetadataProviderClass,
)
from pydajet_metadata._metadata_types import (
    MetadataChild,
    MetadataColumn,
    MetadataObject,
    MetadataProperty,
)
from pydajet_metadata._cache import (
    cache_get_or_set,
    cache_scope_key,
    metadata_tag,
)
from pydajet_metadata.exceptions import (
    MetadataError,
    MetadataNotImplementedError,
)
from pydajet_metadata.settings import get_settings

logger = logging.getLogger(__name__)


def _instantiate_dotnet_guid_list(
    list_cls: type[_NetListClass],
    guid_cls: type[_NetGuidClass],
) -> DotNetGuidList:
    return cast(DotNetGuidList, list_cls.__class_getitem__(guid_cls)())


def _get_metadata_provider() -> type[DotNetMetadataProviderClass] | None:
    """Resolve MetadataProvider from pydajet or dajet test shim."""
    try:
        from pydajet import MetadataProvider

        if MetadataProvider is not None:
            return MetadataProvider
    except ImportError:
        pass

    try:
        import dajet.client as dajet_client

        provider = getattr(dajet_client, "MetadataProvider", None)
        if provider is not None:
            return cast(type[DotNetMetadataProviderClass], provider)
    except Exception:
        return None
    return None


class MetadataClient:
    """Клиент метаданных 1С, работающий поверх DaJet Metadata."""

    PREFIX_MAP: dict[str, str] = {
        "Справочник.": "Справочники",
        "Документ.": "Документы",
        "Константа.": "Константы",
        "Перечисление.": "Перечисления",
        "ПланВидовХарактеристик.": "ПланыВидовХарактеристик",
        "РегистрСведений.": "РегистрыСведений",
        "РегистрНакопления.": "РегистрыНакопления",
        "РегистрБухгалтерии.": "РегистрыБухгалтерии",
        "ПланСчетов.": "ПланыСчетов",
        "ПланОбмена.": "ПланыОбмена",
        "ОпределяемыйТип.": "ОпределяемыеТипы",
        "Задача.": "Задачи",
        "БизнесПроцесс.": "БизнесПроцессы",
    }

    def __init__(self, connection_string: str, data_source: str = "postgresql") -> None:
        provider_cls = _get_metadata_provider()
        if provider_cls is None:
            raise MetadataError(
                "MetadataProvider is not available. Ensure pydajet/.NET runtime is installed."
            )
        if DataSourceType is None:
            raise MetadataError(
                "DataSourceType is not available. Ensure pydajet/.NET runtime is installed."
            )

        ds = (
            DataSourceType.PostgreSql
            if data_source == "postgresql"
            else DataSourceType.SqlServer
        )
        created = provider_cls.Create(ds, connection_string)
        self._provider = cast(DotNetMetadataProvider, created[0] if isinstance(created, tuple) else created)
        configurations_obj = self._provider.GetConfigurations()
        configurations = cast(list[object], configurations_obj)
        if len(configurations) == 0:
            raise MetadataError("DaJet provider returned no configurations")
        self._config = cast(DotNetConfiguration, configurations[0])
        self._type_map = self._build_type_map()
        self.platform_version = int(getattr(self._provider, "PlatformVersion", 0))
        self._cache_scope = cache_scope_key(connection_string, data_source)

    def _create_guid_list(self, guids: Iterable[object]) -> DotNetGuidList:
        if List is None or Guid is None:
            raise MetadataError(
                "DaJet generic collection types are unavailable. Ensure pythonnet and .NET runtime are initialized."
            )
        entity_list = _instantiate_dotnet_guid_list(List, Guid)
        for guid in guids:
            entity_list.Add(guid)
        return entity_list

    def _resolve_reference_names(self, guids: Iterable[object]) -> list[str]:
        entity_list = self._create_guid_list(guids)
        result = self._provider.ResolveReferences(entity_list)
        names = result[0] if isinstance(result, tuple) else result
        if names is None:
            return []
        resolved = cast(DotNetGuidList, names)
        return [resolved[i] for i in range(resolved.Count) if resolved[i]]

    def _build_type_map(self) -> dict[object, str]:
        type_map: dict[object, str] = {}
        metadata: DotNetMetadataIndex = self._config.Metadata
        for type_uuid in metadata.Keys:
            guids_obj = metadata[type_uuid]
            if not isinstance(guids_obj, Iterable):
                continue
            guids = guids_obj
            if isinstance(guids, Sized) and len(guids) == 0:
                continue
            names = self._resolve_reference_names(guids)
            if names:
                type_map[type_uuid] = self._type_by_prefix(names[0])
        return type_map

    @classmethod
    def _type_by_prefix(cls, name: str) -> str:
        for prefix, t in cls.PREFIX_MAP.items():
            if name.startswith(prefix):
                return t
        return "Неизвестный"

    @property
    def config_name(self) -> str:
        return str(self._config.Name)

    @property
    def config_alias(self) -> str | None:
        alias = self._config.Alias
        return str(alias) if alias is not None else None

    def list_types(self) -> list[str]:
        """Возвращает список типов метаданных (справочники, документы и т.д.)."""
        settings = get_settings()
        return cache_get_or_set(
            scope=self._cache_scope,
            category="metadata",
            suffix="types",
            ttl=settings.cache_ttl_metadata,
            tags=(metadata_tag(self._cache_scope),),
            factory=lambda: sorted(set(self._type_map.values())),
        )

    def list_objects(self, type_name: str) -> list[MetadataObject]:
        """Возвращает список объектов указанного типа вместе со схемой и табличными частями."""
        settings = get_settings()
        return cache_get_or_set(
            scope=self._cache_scope,
            category="metadata",
            suffix=f"objects:{type_name}",
            ttl=settings.cache_ttl_metadata,
            tags=(metadata_tag(self._cache_scope),),
            factory=lambda: self._list_objects_uncached(type_name),
        )

    def _list_objects_uncached(self, type_name: str) -> list[MetadataObject]:
        result: list[MetadataObject] = []
        metadata_index: DotNetMetadataIndex = self._config.Metadata
        for type_uuid, detected_type in self._type_map.items():
            if detected_type != type_name:
                continue
            guids_obj = metadata_index[type_uuid]
            if not isinstance(guids_obj, Iterable):
                continue
            names = self._resolve_reference_names(guids_obj)
            for name in names:
                entity = self._get_entity(name)
                if not entity:
                    continue
                result.append(
                    {
                        "name": name,
                        "short_name": name.split(".")[-1] if "." in name else name,
                        "table": str(entity.DbName),
                        "properties": self._extract_properties(entity),
                        "children": self._extract_children(entity),
                    }
                )
            break
        return result

    def _extract_properties(self, entity: DotNetEntity) -> list[MetadataProperty]:
        props: list[MetadataProperty] = []
        properties = entity.Properties
        if properties is not None:
            for prop in properties:
                cols: list[MetadataColumn] = []
                if prop.Columns and prop.Columns.Count > 0:
                    for col in prop.Columns:
                        cols.append(
                            {
                                "name": str(col.Name),
                                "type": str(col.Type) if col.Type else None,
                            }
                        )
                props.append({"name": str(prop.Name), "columns": cols})
        return props

    def _extract_children(self, entity: DotNetEntity) -> list[MetadataChild]:
        children: list[MetadataChild] = []
        entities = entity.Entities
        if entities is not None and entities.Count > 0:
            for child in entities:
                child_entity: DotNetEntity = child
                children.append(
                    {
                        "name": str(child_entity.Name),
                        "table": str(child_entity.DbName),
                        "properties": self._extract_properties(child_entity),
                    }
                )
        return children

    def _get_entity(self, name: str) -> DotNetEntity | None:
        try:
            result = self._provider.GetMetadataObject(name)
            entity = result[0] if isinstance(result, tuple) else result
            return cast(DotNetEntity, entity) if entity is not None else None
        except NotImplementedError as exc:
            logger.debug("GetMetadataObject not implemented for '%s': %s", name, exc)
            raise MetadataNotImplementedError(
                f"Metadata object '{name}' is not implemented: {exc}"
            ) from exc
        except AttributeError as exc:
            logger.debug("Metadata object '%s' not found: %s", name, exc)
            return None
        except Exception as exc:
            logger.error(
                "Unexpected error getting metadata for '%s': %s", name, exc, exc_info=True
            )
            raise MetadataError(f"Failed to get metadata for '{name}': {exc}") from exc
