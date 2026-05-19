"""Низкоуровневый клиент для чтения метаданных 1С через DaJet Metadata."""

import logging
from typing import Any, Optional

from pydajet import DataSourceType, Guid, List
from pydajet_metadata.exceptions import (
    MetadataError,
    MetadataNotImplementedError,
)

logger = logging.getLogger(__name__)


def _get_metadata_provider():
    """Resolve the metadata provider, preferring real pydajet and falling back to dajet.client for tests."""
    try:
        from pydajet import MetadataProvider

        if MetadataProvider is not None:
            return MetadataProvider
    except ImportError:
        pass

    try:
        import dajet.client as dajet_client

        return getattr(dajet_client, "MetadataProvider", None)
    except Exception:
        return None


MetadataProvider = _get_metadata_provider()


class MetadataClient:
    """Клиент метаданных 1С, работающий поверх DaJet Metadata."""

    PREFIX_MAP = {
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

    def __init__(self, connection_string: str, data_source: str = "postgresql"):
        provider = _get_metadata_provider()
        if provider is None:
            raise MetadataError(
                "MetadataProvider is not available. Ensure pydajet/.NET runtime is installed."
            )

        ds = (
            DataSourceType.PostgreSql
            if data_source == "postgresql"
            else DataSourceType.SqlServer
        )
        result = provider.Create(ds, connection_string)
        self._provider = result[0] if isinstance(result, tuple) else result
        configurations = self._provider.GetConfigurations()
        if len(configurations) == 0:
            raise MetadataError("DaJet provider returned no configurations")
        self._config = configurations[0]
        self._type_map = self._build_type_map()
        self.platform_version = getattr(self._provider, "PlatformVersion", 0)

    def _create_guid_list(self, guids: Any):
        if List is None or Guid is None:
            raise MetadataError(
                "DaJet generic collection types are unavailable. Ensure pythonnet and .NET runtime are initialized."
            )
        entity_list = List[Guid]()
        for guid in guids:
            entity_list.Add(guid)
        return entity_list

    def _resolve_reference_names(self, guids: Any) -> list[str]:
        entity_list = self._create_guid_list(guids)
        result = self._provider.ResolveReferences(entity_list)
        names = result[0] if isinstance(result, tuple) else result
        if names is None:
            return []
        return [names[i] for i in range(names.Count) if names[i]]

    def _build_type_map(self) -> dict:
        """Строит карту типов метаданных на основе конфигурации 1С."""
        type_map = {}
        for type_uuid in self._config.Metadata.Keys:
            guids = self._config.Metadata[type_uuid]
            if len(guids) == 0:
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
        return self._config.Name

    @property
    def config_alias(self) -> Optional[str]:
        return self._config.Alias

    def list_types(self) -> list[str]:
        """Возвращает список типов метаданных (справочники, документы и т.д.)."""
        return sorted(set(self._type_map.values()))

    def list_objects(self, type_name: str) -> list[dict]:
        """Возвращает список объектов указанного типа вместе со схемой и табличными частями."""
        result = []
        for type_uuid, detected_type in self._type_map.items():
            if detected_type != type_name:
                continue
            guids = self._config.Metadata[type_uuid]
            names = self._resolve_reference_names(guids)
            for name in names:
                entity = self._get_entity(name)
                if not entity:
                    continue
                result.append(
                    {
                        "name": name,
                        "short_name": name.split(".")[-1] if "." in name else name,
                        "table": entity.DbName,
                        "properties": self._extract_properties(entity),
                        "children": self._extract_children(entity),
                    }
                )
            break
        return result

    def _extract_properties(self, entity) -> list[dict]:
        props = []
        if entity.Properties:
            for prop in entity.Properties:
                cols = []
                if prop.Columns and prop.Columns.Count > 0:
                    for col in prop.Columns:
                        cols.append(
                            {
                                "name": col.Name,
                                "type": str(col.Type) if col.Type else None,
                            }
                        )
                props.append({"name": prop.Name, "columns": cols})
        return props

    def _extract_children(self, entity) -> list[dict]:
        children = []
        if entity.Entities and entity.Entities.Count > 0:
            for child in entity.Entities:
                children.append(
                    {
                        "name": child.Name,
                        "table": child.DbName,
                        "properties": self._extract_properties(child),
                    }
                )
        return children

    def _get_entity(self, name: str):
        """
        Получает EntityDefinition по имени объекта.

        Args:
            name: полное имя объекта (например, "Справочник.Контрагенты")

        Returns:
            EntityDefinition или None

        Raises:
            MetadataNotImplementedError: для неподдерживаемых типов
        """
        try:
            result = self._provider.GetMetadataObject(name)
            return result[0] if isinstance(result, tuple) else result
        except NotImplementedError as e:
            logger.debug("GetMetadataObject not implemented for '%s': %s", name, e)
            raise MetadataNotImplementedError(
                f"Metadata object '{name}' is not implemented: {e}"
            ) from e
        except AttributeError as e:
            logger.debug("Metadata object '%s' not found: %s", name, e)
            return None
        except Exception as e:
            logger.error(
                "Unexpected error getting metadata for '%s': %s", name, e, exc_info=True
            )
            raise MetadataError(f"Failed to get metadata for '{name}': {e}") from e
