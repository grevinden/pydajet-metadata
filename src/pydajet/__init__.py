"""
dajet — Слой метаданных. Взаимодействие с .NET Runtime и DaJet Metadata.
"""
from os import environ
from pathlib import Path
from typing import Final

from pydajet._platform import find_binary_folder

PATH_BIN: Final [ Path ] = find_binary_folder ( )

# Указываем путь к runtimeconfig.json
runtime_config = PATH_BIN / "DaJet.Metadata.runtimeconfig.json"
if runtime_config.exists ( ) :
    environ [ "PYTHONNET_RUNTIME_CONFIG" ] = str ( runtime_config )

# DOTNET_ROOT всё ещё нужен для поиска нативных библиотек
environ.setdefault ( "DOTNET_ROOT" , str ( PATH_BIN ) )

import clr  # noqa

for dll in ("TypeSystem", "Data", "Metadata"):# pragma: no cover
    clr.AddReference ( str ( PATH_BIN / f"DaJet.{dll}.dll" ) )  # noqa

from DaJet.Metadata import MetadataProvider  # noqa
from DaJet.Data import DataSourceType  # noqa
from System import Guid  # noqa
from System.Collections.Generic import List  # noqa

from sqlalchemy.dialects.postgresql import VARCHAR
from sqlalchemy.dialects.postgresql.base import ischema_names
ischema_names['mvarchar'] = VARCHAR

from pydajet.client import MetadataClient
from pydajet._uuid import from_1c, to_1c, generate, format_uuid

__all__ = [
    'MetadataProvider' , 'DataSourceType' , 'Guid' , 'List' ,  # noqa
    'MetadataClient' , 'from_1c' , 'to_1c' , 'generate' , 'format_uuid' ,
]
