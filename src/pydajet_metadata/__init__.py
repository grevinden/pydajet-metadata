"""
pydajet_metadata — Прикладной слой для работы с данными 1С.
"""

from typing import Any, TypeAlias

# Протоколы (typing.Protocol) для структурной типизации
from pydajet_metadata.protocols import (
    IColumnMapper,
    IMetadataClient,
    IRepository,
    ISession,
    IQuery,
)

# Чистые утилиты (без .NET)
from pydajet_metadata.api import APIGenerator
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
RowDict: TypeAlias = dict[str, Any]  # Строка БД как словарь

__all__ = [
    # Протоколы
    "ISession",
    "IQuery",
    "IColumnMapper",
    "IMetadataClient",
    "IRepository",
    # Реализации
    "Repository",
    "Query",
    "Session",
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
