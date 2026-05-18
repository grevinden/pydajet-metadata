"""
Протоколы (typing.Protocol) для структурной типизации pydajet_metadata.

PEP 544: Protocols позволяют использовать duck-typing со статической проверкой.
Классы НЕ обязаны наследоваться от Protocol — достаточно реализовать методы.
Наследование добавлено только для явности и документации.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import (
    Any,
    Dict,
    Iterator,
    List,
    Optional,
    Protocol,
    Sequence,
    Tuple,
    runtime_checkable,
)

from typing_extensions import Literal


# ─── Type Aliases ────────────────────────────────────────────────────────────
UUIDString = str  # "5000289c-66b6-fadf-11f1-4e880e761abe"
ConnectionString = str  # "Host=...;Port=...;Database=...;..."
TableName = str  # "_Reference53"
HumanName = str  # "Наименование"
DbColumnName = str  # "_Description"
RowDict = Dict[str, Any]  # Строка БД как словарь
ColumnMap = Dict[HumanName, DbColumnName]  # Маппинг имён колонок


# ─── Protocols ───────────────────────────────────────────────────────────────

@runtime_checkable
class ISession(Protocol):
    """Интерфейс подключения к БД и управления транзакциями."""

    @property
    def engine(self) -> Any:
        """SQLAlchemy Engine или активное Connection."""
        ...

    def reflect_table(self, table_name: str) -> Any:
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

    def human_to_db(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Преобразует {human_name: value} → {db_name: value}."""
        ...

    def db_to_human(self, row: Any) -> Dict[str, Any]:
        """Преобразует строку БД → {human_name: value}."""
        ...

    def get_db_column(self, human_name: str) -> Any:
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
    def _table(self) -> Any:
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

    def where(self, *conditions: Any) -> IQuery:
        """Добавляет WHERE-условия и возвращает self."""
        ...

    # ─── Write ───────────────────────────────────────────────────────────
    def insert(self, data: Dict[str, Any], extra: Optional[Dict[str, Any]] = None) -> UUIDString:
        """Вставляет запись и возвращает UUID."""
        ...

    def update(self, record_id: UUIDString, data: Dict[str, Any]) -> bool:
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
        data: Dict[str, Any],
        expected_version: Optional[int] = None,
    ) -> bool:
        """Обновляет с оптимистичной блокировкой по _Version."""
        ...

    def БезопасноеИзменить(self, record_id: UUIDString, data: Dict[str, Any]) -> bool:
        """Безопасное обновление с автоматической проверкой версии."""
        ...

    def ПолучитьВерсию(self, record_id: UUIDString) -> int:
        """Возвращает текущую версию объекта (_Version)."""
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

    def list_objects(self, type_name: str) -> List[Dict[str, Any]]:
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

    def __getattr__(self, name: str) -> Any:
        """Доступ к TypeAccessor: repo.Справочники.Контрагенты."""
        ...
