"""
dajet — Слой метаданных. Взаимодействие с .NET Runtime и DaJet Metadata.
"""
from os import environ
from dajet._platform import find_binary_folder

environ.setdefault("PYTHONNET_RUNTIME", "coreclr")

import clr  # noqa

for dll in ("TypeSystem", "Data", "Metadata"):
    clr.AddReference(str(find_binary_folder() / f"DaJet.{dll}.dll"))  # noqa

from DaJet.Metadata import MetadataProvider  # noqa
from DaJet.Data import DataSourceType  # noqa
from System import Guid  # noqa
from System.Collections.Generic import List  # noqa

from sqlalchemy.dialects.postgresql import VARCHAR
from sqlalchemy.dialects.postgresql.base import ischema_names
ischema_names['mvarchar'] = VARCHAR

from dajet.client import MetadataClient
from dajet._uuid import from_1c, to_1c, generate, format_uuid

__all__ = [
    'MetadataProvider',
    'DataSourceType',
    'Guid',
    'List',
    'MetadataClient',
    'from_1c',
    'to_1c',
    'generate',
    'format_uuid',
]
