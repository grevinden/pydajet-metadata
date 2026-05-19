"""
pydajet_metadata — Прикладной слой для работы с данными 1С.
"""

from typing import TypeAlias

# Протоколы (typing.Protocol) для структурной типизации
from pydajet_metadata.protocols import (
    IAsyncQuery,
    IAsyncRepository,
    IAsyncSession,
    IAsyncMetadataClient,
    IColumnMapper,
    IMetadataClient,
    IRepository,
    ISession,
    IQuery,
)

# Чистые утилиты (без .NET)
from pydajet_metadata.api import APIGenerator
from pydajet_metadata.async_query import AsyncQuery
from pydajet_metadata.async_repository import AsyncRepository
from pydajet_metadata.async_session import AsyncSession
from pydajet_metadata.bridge import PolarsBridge
from pydajet_metadata.query import Query
from pydajet_metadata.repository import Repository
from pydajet_metadata.schema import SchemaGenerator
from pydajet_metadata.session import Session

UUIDString: TypeAlias = str  # UUID с дефисами: "5000289c-66b6-fadf-11f1-4e880e761abe"
ConnectionString: TypeAlias = str  # "Host=...;Port=...;Database=...;..."
TableName: TypeAlias = str  # "_Reference53"
HumanName: TypeAlias = str  # "Наименование"
DbColumnName: TypeAlias = str  # "_Description"
RowDict: TypeAlias = dict[str, object]  # Строка БД как словарь

__all__ = [
    # Протоколы
    "ISession",
    "IQuery",
    "IAsyncQuery",
    "IAsyncSession",
    "IAsyncRepository",
    "IAsyncMetadataClient",
    "IColumnMapper",
    "IMetadataClient",
    "IRepository",
    # Реализации
    "Repository",
    "AsyncRepository",
    "Query",
    "AsyncQuery",
    "Session",
    "AsyncSession",
    "SchemaGenerator",
    "PolarsBridge",
    "APIGenerator",
    # Типы
    "UUIDString",
    "ConnectionString",
    "TableName",
    "HumanName",
    "DbColumnName",
    "RowDict",
]
