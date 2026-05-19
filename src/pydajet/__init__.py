"""
dajet — Слой метаданных. Взаимодействие с .NET Runtime и DaJet Metadata.
"""

from __future__ import annotations

from os import environ
from pathlib import Path
from typing import Final, cast

from pydajet._dotnet import (
    DataSourceTypeType,
    GenericListType,
    GuidType,
    MetadataProviderType,
)
from pydajet._platform import find_binary_folder

PATH_BIN: Final[Path] = find_binary_folder()

runtime_config = PATH_BIN / "DaJet.Metadata.runtimeconfig.json"
if runtime_config.exists():
    environ["PYTHONNET_RUNTIME_CONFIG"] = str(runtime_config)

environ.setdefault("DOTNET_ROOT", str(PATH_BIN))

MetadataProvider: MetadataProviderType = None
DataSourceType: DataSourceTypeType = None
Guid: GuidType = None
List: GenericListType = None

try:  # pragma: no cover - optional runtime
    import clr

    for dll in ("TypeSystem", "Data", "Metadata"):
        clr.AddReference(str(PATH_BIN / f"DaJet.{dll}.dll"))

    from DaJet.Data import DataSourceType as _DataSourceType
    from DaJet.Metadata import MetadataProvider as _MetadataProvider
    from System import Guid as _Guid
    from System.Collections.Generic import List as _List

    MetadataProvider = cast(MetadataProviderType, _MetadataProvider)
    DataSourceType = cast(DataSourceTypeType, _DataSourceType)
    Guid = cast(GuidType, _Guid)
    List = cast(GenericListType, _List)
except Exception:
    MetadataProvider = None

    class _FallbackDataSourceType:
        PostgreSql = "PostgreSql"
        SqlServer = "SqlServer"

    DataSourceType = cast(DataSourceTypeType, _FallbackDataSourceType)
    Guid = None
    List = None

from sqlalchemy.dialects.postgresql import VARCHAR
from sqlalchemy.dialects.postgresql.base import ischema_names

ischema_names["mvarchar"] = VARCHAR

MetadataClient: type | None
try:
    from pydajet.client import MetadataClient as _MetadataClient

    MetadataClient = _MetadataClient
except Exception:
    MetadataClient = None

from pydajet._uuid import format_uuid, from_1c, generate, to_1c

__all__ = [
    "MetadataProvider",
    "DataSourceType",
    "Guid",
    "List",
    "MetadataClient",
    "from_1c",
    "to_1c",
    "generate",
    "format_uuid",
]
