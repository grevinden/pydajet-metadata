"""Репозиторий объектов 1С."""

from typing import TYPE_CHECKING, Any

from pydajet_metadata.query import Query
from pydajet_metadata.session import Session

if TYPE_CHECKING:
    from pydajet_metadata.protocols import IMetadataClient, IRepository, ISession


class Repository:  # Структурно соответствует IRepository
    def __init__(
        self,
        connection_string: str | None = None,
        data_source: str = "postgresql",
        *,
        client: "IMetadataClient | None" = None,
        session: "ISession | None" = None,
    ):
        # Ленивый импорт — только когда создаётся экземпляр
        from pydajet.client import MetadataClient

        # Поддержка DI через протоколы (приоритет) или создание внутри (обратная совместимость)
        if client is not None:
            self._client = client
        else:
            if not connection_string:
                raise ValueError("connection_string is required when client is not provided")
            self._client = MetadataClient(connection_string, data_source)

        if session is not None:
            self._session = session
        else:
            if not connection_string:
                raise ValueError("connection_string is required when session is not provided")
            self._session = Session(connection_string)

        self._queries: dict[str, dict[str, Query]] = {}

        # Сохраняем идентификатор версии метаданных
        self._root_guid = self._get_root_guid()
        self._metadata_version = self._client.platform_version

        self._build()

    def _build(self):
        for type_name in self._client.list_types():
            self._queries[type_name] = {}
            for obj in self._client.list_objects(type_name):
                column_map = {}
                pk = "_idrref"
                for prop in obj["properties"]:
                    if prop["columns"]:
                        db_name = prop["columns"][0]["name"]
                        column_map[prop["name"]] = db_name
                        if db_name.lower() in ("_idrref", "_recordkey"):
                            pk = db_name.lower()

                table_name = obj["table"]
                pk = self._session.get_pk(table_name) or pk

                query = Query(self._session, table_name, column_map, pk)

                for child in obj["children"]:
                    child_map = {}
                    child_pk = "_idrref"
                    child_owner = "_idrref"
                    for prop in child["properties"]:
                        if prop["columns"]:
                            db_name = prop["columns"][0]["name"]
                            child_map[prop["name"]] = db_name
                            if db_name.lower() in ("_idrref", "_recordkey"):
                                child_pk = db_name.lower()
                            if (
                                db_name.lower().endswith("_rref")
                                and db_name.lower() != child_pk
                            ):
                                child_owner = db_name.lower()

                    child_table = child["table"]
                    child_pk = self._session.get_pk(child_table) or child_pk
                    child_query = Query(
                        self._session, child_table, child_map, child_pk, child_owner
                    )
                    query._children[child["name"]] = child_query
                    setattr(query, child["name"], child_query)

                self._queries[type_name][obj["short_name"]] = query

    def types(self) -> list[str]:
        return sorted(self._queries.keys())

    def objects(self, type_name: str) -> list[str]:
        if type_name not in self._queries:
            return []
        return sorted(self._queries[type_name].keys())

    def query(self, type_name: str, object_name: str) -> Query:
        if type_name not in self._queries:
            raise KeyError(f"Type '{type_name}' not found")
        if object_name not in self._queries[type_name]:
            raise KeyError(f"Object '{object_name}' not found in '{type_name}'")
        return self._queries[type_name][object_name]

    def __getattr__(self, name: str):
        if name in self._queries:
            return TypeAccessor(self, name)
        raise AttributeError(f"Type '{name}' not found")

    @property
    def session(self) -> "ISession":
        return self._session

    def close(self):
        self._session.close()

    def _get_root_guid(self) -> str:
        """
        Получает корневой GUID конфигурации.
        """
        try:
            from sqlalchemy import select

            config_table = self._session.reflect_table("_Config")
            stmt = select(config_table.c._FileName)
            with self._session.engine.connect() as conn:
                result = conn.execute(stmt).scalar()
                return result.hex() if result else ""
        except Exception:
            return ""

    def check_metadata_actual(self):
        """
        Проверяет актуальность метаданных конфигурации.

        Raises:
            MetadataOutdatedError: если метаданные изменились
        """
        # Ленивый импорт внутри метода
        from pydajet_metadata.exceptions import MetadataOutdatedError

        current_root = self._get_root_guid()
        if current_root and self._root_guid and current_root != self._root_guid:
            raise MetadataOutdatedError(
                f"Metadata configuration has changed.\n"
                f"  Old root GUID: {self._root_guid}\n"
                f"  New root GUID: {current_root}\n"
                f"  All cached metadata objects are outdated.\n"
                f"  Please create a new Repository instance to reload metadata."
            )

    @property
    def root_guid(self) -> str:
        return self._root_guid

    @property
    def metadata_version(self) -> int:
        return self._metadata_version

    def refresh_metadata(self):
        """Принудительно обновляет метаданные."""
        self._root_guid = self._get_root_guid()
        self._queries.clear()
        self._build()


class TypeAccessor:
    def __init__(self, repo: Repository, type_name: str):
        self._repo = repo
        self._type = type_name

    def __getitem__(self, name: str) -> Query:
        return self._repo.query(self._type, name)

    def __getattr__(self, name: str) -> Query:
        return self._repo.query(self._type, name)

    def list(self) -> list[str]:
        return self._repo.objects(self._type)
