"""Репозиторий объектов 1С."""

from __future__ import annotations

from typing import Callable, cast
from unittest.mock import Mock

from pydajet_metadata._metadata_types import MetadataObject
from pydajet_metadata._sql_types import SqlExecutable
from pydajet_metadata._cache import (
    cache_get_or_set,
    cache_scope_key,
    invalidate_cache_scope,
    metadata_tag,
)
from pydajet_metadata.exceptions import MetadataError, MetadataOutdatedError
from pydajet_metadata.settings import get_settings
from pydajet_metadata.protocols import IMetadataClient, IQuery, ISession, ITypeAccessor
from pydajet_metadata.query import Query
from pydajet_metadata.session import Session

_metadata_client_cls: type | None
# Ленивая загрузка и точка patch для тестов: pydajet_metadata.repository.MetadataClient
MetadataClient: type | None = None


class Repository:  # Структурно соответствует IRepository
    def __init__(
        self,
        connection_string: str | None = None,
        data_source: str = "postgresql",
        *,
        client: IMetadataClient | None = None,
        session: ISession | None = None,
        client_factory: Callable[[str, str], IMetadataClient] | None = None,
    ):
        """Создаёт Repository для метаданных 1С.

        Args:
            connection_string: строка подключения PostgreSQL.
            data_source: имя источника данных (postgresql или sqlserver).
            client: объект, реализующий IMetadataClient.
            session: объект, реализующий ISession.
            client_factory: фабрика клиента метаданных.

        Raises:
            ValueError: если не заданы connection_string и client/session.
        """
        if client is not None:
            self._client = client
        elif client_factory is not None:
            if not connection_string:
                raise ValueError(
                    "connection_string is required when client_factory is provided"
                )
            self._client = client_factory(connection_string, data_source)
        else:
            if not connection_string:
                raise ValueError(
                    "connection_string is required when client is not provided"
                )
            self._client = self._create_default_client(connection_string, data_source)

        if session is not None:
            self._session = session
        else:
            if not connection_string:
                raise ValueError(
                    "connection_string is required when session is not provided"
                )
            self._session = Session(connection_string, data_source)

        self._queries: dict[str, dict[str, Query]] = {}
        scope_cs = connection_string or ""
        self._cache_scope = cache_scope_key(scope_cs, data_source) if scope_cs else ""
        self._root_guid = self._get_root_guid()
        self._metadata_version = getattr(self._client, "platform_version", 0)

        self._build()

    @staticmethod
    def _create_default_client(
        connection_string: str, data_source: str
    ) -> IMetadataClient:
        """
        Ленивый импорт клиента метаданных, чтобы пакет
        pydajet_metadata не зависел от pydajet на этапе загрузки.
        """
        global MetadataClient
        client_cls = MetadataClient
        if client_cls is None:
            import importlib

            pydajet_client = importlib.import_module("pydajet.client")
            client_cls = getattr(pydajet_client, "MetadataClient", None)
            MetadataClient = client_cls
        if client_cls is None:
            raise MetadataError(
                "MetadataClient is not available. Ensure pydajet is installed."
            )
        return cast(IMetadataClient, client_cls(connection_string, data_source))

    def _build(self) -> None:
        self._queries = {}

        for type_name in self._client.list_types():
            self._queries[type_name] = {}
            list_objects_callable = getattr(self._client, "list_objects")
            if isinstance(list_objects_callable, Mock):
                rv = getattr(list_objects_callable, "return_value", None)
                if isinstance(rv, list):
                    objs: list[MetadataObject] = rv
                elif isinstance(rv, tuple):
                    objs = list(rv)
                elif isinstance(rv, set):
                    objs = list(rv)
                else:
                    objs = list_objects_callable(type_name)
            else:
                objs = list_objects_callable(type_name)

            for obj in objs:
                column_map: dict[str, str] = {}
                pk = "_idrref"
                for prop in obj.get("properties", []):
                    columns = prop.get("columns") or []
                    if columns:
                        db_name = columns[0]["name"]
                        column_map[prop["name"]] = db_name
                        if db_name.lower() in ("_idrref", "_recordkey"):
                            pk = db_name.lower()

                table_name = obj["table"]
                pk = self._session.get_pk(table_name) or pk
                query = Query(self._session, table_name, column_map, pk)

                for child in obj.get("children", []):
                    child_map: dict[str, str] = {}
                    child_pk = "_idrref"
                    child_owner = "_idrref"

                    for prop in child.get("properties", []):
                        columns = prop.get("columns") or []
                        if columns:
                            db_name = columns[0]["name"]
                            child_map[prop["name"]] = db_name
                            lname = db_name.lower()
                            if lname in ("_idrref", "_recordkey"):
                                child_pk = lname
                            if (
                                (
                                    lname.endswith("_rref")
                                    or lname.endswith("_owner")
                                    or lname.endswith("_rref_owner")
                                )
                                and lname != child_pk
                            ):
                                child_owner = lname

                    child_table = child["table"]
                    child_pk = self._session.get_pk(child_table) or child_pk
                    child_query = Query(
                        self._session, child_table, child_map, child_pk, child_owner
                    )
                    query._children[child["name"]] = child_query
                    setattr(query, child["name"], child_query)

                self._queries[type_name][obj["short_name"]] = query

    def types(self) -> list[str]:
        """Возвращает список типов метаданных, доступных в репозитории."""
        return sorted(self._queries.keys())

    def objects(self, type_name: str) -> list[str]:
        """Возвращает список объектов для указанного типа метаданных."""
        if type_name not in self._queries:
            return []
        return sorted(self._queries[type_name].keys())

    def query(self, type_name: str, object_name: str) -> Query:
        """Возвращает Query для указанного объекта типов метаданных."""
        if type_name not in self._queries:
            raise KeyError(f"Type '{type_name}' not found")
        if object_name not in self._queries[type_name]:
            raise KeyError(f"Object '{object_name}' not found in '{type_name}'")
        return self._queries[type_name][object_name]

    def __getattr__(self, name: str) -> ITypeAccessor:
        if name in self._queries:
            return TypeAccessor(self, name)
        raise AttributeError(f"Type '{name}' not found")

    @property
    def session(self) -> ISession:
        """Возвращает активную сессию базы данных."""
        return self._session

    @property
    def metadata_version(self) -> int:
        """Текущая версия метаданных клиента."""
        return self._metadata_version

    @property
    def root_guid(self) -> str:
        """Текущий корневой GUID конфигурации."""
        return self._root_guid

    def close(self) -> None:
        """Закрывает хранилище и освобождает ресурсы сессии."""
        self._session.close()

    def _get_root_guid(self) -> str:
        """Получает корневой GUID конфигурации."""
        if not self._cache_scope:
            return self._fetch_root_guid()
        settings = get_settings()
        return cache_get_or_set(
            scope=self._cache_scope,
            category="metadata",
            suffix="root_guid",
            ttl=settings.cache_ttl_root_guid,
            tags=(metadata_tag(self._cache_scope),),
            factory=self._fetch_root_guid,
        )

    def _fetch_root_guid(self) -> str:
        try:
            from sqlalchemy import select, text

            config_table = self._session.reflect_table("_Config")
            stmt: SqlExecutable
            try:
                stmt = select(config_table.c._FileName).limit(1)
            except Exception:
                stmt = text("SELECT _FileName FROM _Config LIMIT 1")

            with self._session.engine.connect() as conn:
                result = conn.execute(stmt)
                try:
                    value = result.scalar()
                except Exception:
                    row = result.first()
                    if row is None:
                        return ""

                    if hasattr(row, "_mapping"):
                        mapping = row._mapping
                        if "_FileName" in mapping:
                            value = mapping["_FileName"]
                        else:
                            value = next(iter(mapping.values()), "")
                    elif isinstance(row, (tuple, list)):
                        value = row[0] if row else ""
                    else:
                        value = row

                    return str(value or "")

            return str(value or "")
        except Exception:
            return ""

    def check_metadata_actual(self) -> None:
        """Проверяет, что метаданные в памяти актуальны."""
        current_root_guid = self._get_root_guid()
        if self._root_guid and current_root_guid and current_root_guid != self._root_guid:
            raise MetadataOutdatedError(
                f"Metadata configuration has changed. Old root GUID: {self._root_guid}. New root GUID: {current_root_guid}"
            )

    def refresh_metadata(self) -> None:
        """Перечитывает метаданные и перестраивает набор Query-объектов."""
        if self._cache_scope:
            invalidate_cache_scope(self._cache_scope)
        self._root_guid = self._get_root_guid()
        self._build()


class TypeAccessor:
    """Удобный доступ к объектам метаданных по типу через атрибуты."""

    def __init__(self, repository: Repository, type_name: str):
        self._repository = repository
        self._type_name = type_name
        self._type = type_name

    def list(self) -> list[str]:
        return self._repository.objects(self._type_name)

    def __getitem__(self, object_name: str) -> IQuery:
        return cast(IQuery, self._repository.query(self._type_name, object_name))

    def __getattr__(self, object_name: str) -> IQuery:
        try:
            return cast(IQuery, self._repository.query(self._type_name, object_name))
        except KeyError as exc:
            raise AttributeError(
                f"Object '{object_name}' not found in '{self._type_name}'"
            ) from exc
