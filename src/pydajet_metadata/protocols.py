"""
Протоколы (typing.Protocol) для структурной типизации pydajet_metadata.

PEP 544: Protocols позволяют использовать duck-typing со статической проверкой.
Классы НЕ обязаны наследоваться от Protocol — достаточно реализовать методы.
Наследование добавлено только для явности и документации.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import (
    AsyncContextManager,
    Dict,
    Iterator,
    List,
    Literal,
    Optional,
    Protocol,
    Sequence,
    Tuple,
    runtime_checkable,
)

from pydajet_metadata._metadata_types import MetadataObject
from pydajet_metadata._sql_types import DbRow, SqlColumn, SqlWhereClause
from sqlalchemy.engine import Engine
from sqlalchemy.sql.schema import Table


# ─── Type Aliases ────────────────────────────────────────────────────────────
UUIDString = str  # "5000289c-66b6-fadf-11f1-4e880e761abe"
ConnectionString = str  # "Host=...;Port=...;Database=...;..."
TableName = str  # "_Reference53"
HumanName = str  # "Наименование"
DbColumnName = str  # "_Description"
RowDict = Dict[str, object]  # Строка БД в человекочитаемых именах колонок
ColumnMap = Dict[HumanName, DbColumnName]  # Маппинг имён колонок


# ─── Protocols ───────────────────────────────────────────────────────────────

@runtime_checkable
class ISession(Protocol):
    """Интерфейс подключения к БД и управления транзакциями."""

    @property
    def engine(self) -> Engine:
        """SQLAlchemy Engine."""
        ...

    def reflect_table(self, table_name: str) -> Table:
        """Рефлектирует таблицу БД в SQLAlchemy Table."""
        ...

    def get_pk(self, table_name: str) -> str:
        """Возвращает имя первичного ключа таблицы."""
        ...

    @contextmanager
    def transaction(self) -> Iterator[ISession]:
        """Контекстный менеджер транзакции с авто-commit/rollback."""
        ...

    @contextmanager
    def savepoint(self) -> Iterator[ISession]:
        """Контекстный менеджер вложенной транзакции (SAVEPOINT)."""
        ...

    def close(self) -> None:
        """Закрывает соединение и освобождает ресурсы."""
        ...


@runtime_checkable
class IColumnMapper(Protocol):
    """Интерфейс маппинга имён и значений колонок human ↔ db."""

    def human_to_db(self, data: RowDict) -> dict[str, object]:
        """Преобразует {human_name: value} → {db_name: value}."""
        ...

    def db_to_human(self, row: DbRow) -> RowDict:
        """Преобразует строку БД → {human_name: value}."""
        ...

    def get_db_column(self, human_name: str) -> SqlColumn:
        """Возвращает SQLAlchemy Column по человеческому имени."""
        ...

    @property
    def human_names(self) -> List[str]:
        """Список человеческих имён колонок."""
        ...

    @property
    def db_names(self) -> List[str]:
        """Список имён колонок в БД."""
        ...


@runtime_checkable
class IQuery(Protocol):
    """Интерфейс построителя запросов к таблицам 1С."""

    # ─── Properties ──────────────────────────────────────────────────────
    @property
    def _table(self) -> Table:
        """SQLAlchemy Table."""
        ...

    @property
    def _pk(self) -> str:
        """Имя колонки первичного ключа."""
        ...

    @property
    def _owner_key(self) -> str:
        """Имя колонки владельца для табличных частей."""
        ...

    @property
    def _children(self) -> Dict[str, IQuery]:
        """Словарь дочерних запросов (табличные части)."""
        ...

    @property
    def _column_map(self) -> ColumnMap:
        """Маппинг human_name → db_name."""
        ...

    # ─── Read ────────────────────────────────────────────────────────────
    def all(self) -> List[RowDict]:
        """Возвращает все строки таблицы."""
        ...

    def first(self) -> Optional[RowDict]:
        """Возвращает первую строку или None."""
        ...

    def count(self) -> int:
        """Возвращает количество строк."""
        ...

    def where(self, *conditions: SqlWhereClause) -> IQuery:
        """Добавляет WHERE-условия и возвращает self."""
        ...

    # ─── Write ───────────────────────────────────────────────────────────
    def insert(self, data: RowDict, extra: Optional[RowDict] = None) -> UUIDString:
        """Вставляет запись и возвращает UUID."""
        ...

    def update(self, record_id: UUIDString, data: RowDict) -> bool:
        """Обновляет запись по UUID. Возвращает True если изменена."""
        ...

    def delete(self, record_id: UUIDString) -> bool:
        """Удаляет запись по UUID. Возвращает True если удалена."""
        ...

    # ─── Locking & Versioning ────────────────────────────────────────────
    def lock(
        self,
        mode: Literal["exclusive", "shared"] = "exclusive",
        row_id: Optional[UUIDString] = None,
        nowait: bool = False,
    ) -> None:
        """Блокирует таблицу или строку."""
        ...

    def Изменить(
        self,
        record_id: UUIDString,
        data: RowDict,
        expected_version: Optional[int] = None,
    ) -> bool:
        """Обновляет с оптимистичной блокировкой по _Version."""
        ...

    def БезопасноеИзменить(self, record_id: UUIDString, data: RowDict) -> bool:
        """Безопасное обновление с автоматической проверкой версии."""
        ...

    def ПолучитьВерсию(self, record_id: UUIDString) -> int:
        """Возвращает текущую версию объекта (_Version)."""
        ...


@runtime_checkable
class IAsyncQuery(Protocol):
    """Асинхронный интерфейс построителя запросов к таблицам 1С."""

    @property
    def _table(self) -> Table:
        ...

    @property
    def _pk(self) -> str:
        ...

    @property
    def _owner_key(self) -> str:
        ...

    @property
    def _children(self) -> Dict[str, "IAsyncQuery"]:
        ...

    @property
    def _column_map(self) -> ColumnMap:
        ...

    async def all(self) -> List[RowDict]:
        ...

    async def first(self) -> Optional[RowDict]:
        ...

    async def count(self) -> int:
        ...

    def where(self, *conditions: SqlWhereClause) -> "IAsyncQuery":
        ...

    async def insert(self, data: RowDict, extra: Optional[RowDict] = None) -> UUIDString:
        ...

    async def update(self, record_id: UUIDString, data: RowDict) -> bool:
        ...

    async def delete(self, record_id: UUIDString) -> bool:
        ...

    async def lock(
        self,
        mode: Literal["exclusive", "shared"] = "exclusive",
        row_id: Optional[UUIDString] = None,
        nowait: bool = False,
    ) -> None:
        ...

    async def Изменить(
        self,
        record_id: UUIDString,
        data: RowDict,
        expected_version: Optional[int] = None,
    ) -> bool:
        ...

    async def БезопасноеИзменить(self, record_id: UUIDString, data: RowDict) -> bool:
        ...

    async def ПолучитьВерсию(self, record_id: UUIDString) -> int:
        ...


@runtime_checkable
class ITypeAccessor(Protocol):
    """Доступ к объектам одного типа метаданных: repo.Справочники.Контрагенты."""

    def list(self) -> List[str]:
        ...

    def __getitem__(self, object_name: str) -> "IQuery":
        ...

    def __getattr__(self, object_name: str) -> "IQuery":
        ...


@runtime_checkable
class IAsyncSession(Protocol):
    """Асинхронный интерфейс подключения к БД и управления транзакциями."""

    @property
    def engine(self) -> Engine:
        ...

    async def reflect_table(self, table_name: str) -> Table:
        ...

    async def get_pk(self, table_name: str) -> str:
        ...

    def transaction(self) -> AsyncContextManager["IAsyncSession"]:
        ...

    def savepoint(self) -> AsyncContextManager["IAsyncSession"]:
        ...

    async def close(self) -> None:
        ...


@runtime_checkable
class IAsyncRepository(Protocol):
    """Асинхронный интерфейс репозитория объектов 1С."""

    @property
    def session(self) -> IAsyncSession:
        ...

    @property
    def root_guid(self) -> str:
        ...

    @property
    def metadata_version(self) -> int:
        ...

    async def types(self) -> List[str]:
        ...

    async def objects(self, type_name: str) -> List[str]:
        ...

    async def query(self, type_name: str, object_name: str) -> IAsyncQuery:
        ...

    async def check_metadata_actual(self) -> None:
        ...

    async def refresh_metadata(self) -> None:
        ...

    async def close(self) -> None:
        ...

    def __getattr__(self, name: str) -> ITypeAccessor:
        ...


@runtime_checkable
class IAsyncMetadataClient(Protocol):
    """Асинхронный интерфейс клиента метаданных 1С."""

    @property
    def platform_version(self) -> int:
        ...

    async def list_types(self) -> List[str]:
        ...

    async def list_objects(self, type_name: str) -> List[MetadataObject]:
        ...


@runtime_checkable
class IMetadataClient(Protocol):
    """Интерфейс клиента метаданных 1С (.NET DaJet)."""

    @property
    def platform_version(self) -> int:
        """Версия платформы 1С."""
        ...

    def list_types(self) -> List[str]:
        """Возвращает список типов метаданных (Справочники, Документы, ...)."""
        ...

    def list_objects(self, type_name: str) -> List[MetadataObject]:
        """Возвращает список объектов типа с метаданными (table, properties, children)."""
        ...


@runtime_checkable
class IRepository(Protocol):
    """Интерфейс репозитория объектов 1С."""

    @property
    def session(self) -> ISession:
        """Активная сессия БД."""
        ...

    @property
    def root_guid(self) -> str:
        """Корневой GUID конфигурации."""
        ...

    @property
    def metadata_version(self) -> int:
        """Версия метаданных платформы."""
        ...

    def types(self) -> List[str]:
        """Список типов метаданных."""
        ...

    def objects(self, type_name: str) -> List[str]:
        """Список объектов типа."""
        ...

    def query(self, type_name: str, object_name: str) -> IQuery:
        """Возвращает Query для объекта."""
        ...

    def check_metadata_actual(self) -> None:
        """Проверяет актуальность метаданных. Raises MetadataOutdatedError."""
        ...

    def refresh_metadata(self) -> None:
        """Принудительно обновляет кэш метаданных."""
        ...

    def close(self) -> None:
        """Закрывает репозиторий и сессию."""
        ...

    def __getattr__(self, name: str) -> ITypeAccessor:
        """Доступ к TypeAccessor: repo.Справочники.Контрагенты."""
        ...
