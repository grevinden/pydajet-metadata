"""
dajet — Слой метаданных. Взаимодействие с .NET Runtime и DaJet Metadata.
"""

from os import environ
from pathlib import Path
from typing import Final

from pydajet._platform import find_binary_folder

PATH_BIN: Final[Path] = find_binary_folder()

# Указываем путь к runtimeconfig.json
runtime_config = PATH_BIN / "DaJet.Metadata.runtimeconfig.json"
if runtime_config.exists():
    environ["PYTHONNET_RUNTIME_CONFIG"] = str(runtime_config)

# DOTNET_ROOT всё ещё нужен для поиска нативных библиотек
environ.setdefault("DOTNET_ROOT", str(PATH_BIN))

# Попытка импортировать CLR и DaJet — если среда без .NET, не падаем при импорте
MetadataProvider = None
DataSourceType = None
Guid = None
List = None
try:  # pragma: no cover - optional runtime
    import clr  # type: ignore

    for dll in ("TypeSystem", "Data", "Metadata"):
        clr.AddReference(str(PATH_BIN / f"DaJet.{dll}.dll"))

    from DaJet.Metadata import MetadataProvider  # type: ignore
    from DaJet.Data import DataSourceType  # type: ignore
    from System import Guid  # type: ignore
    from System.Collections.Generic import List  # type: ignore
except Exception:
    # Оставляем значения None — код, требующий DaJet, должен корректно обработать это.
    MetadataProvider = None
    # Фоллбэк для DataSourceType — простой контейнер значений, используемый в тестах
    class _FallbackDataSourceType:
        PostgreSql = "PostgreSql"
        SqlServer = "SqlServer"

    DataSourceType = _FallbackDataSourceType
    Guid = None
    List = None

from sqlalchemy.dialects.postgresql import VARCHAR
from sqlalchemy.dialects.postgresql.base import ischema_names

ischema_names["mvarchar"] = VARCHAR

try:
    from pydajet.client import MetadataClient
except Exception:
    MetadataClient = None

from pydajet._uuid import format_uuid, from_1c, generate, to_1c

__all__ = [
    "MetadataProvider",
    "DataSourceType",
    "Guid",
    "List",  # noqa
    "MetadataClient",
    "from_1c",
    "to_1c",
    "generate",
    "format_uuid",
]
