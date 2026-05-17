"""
pydajet_metadata — Прикладной слой для работы с данными 1С.
"""
# Чистые утилиты (без .NET)
from pydajet_metadata._uuid import from_1c , to_1c , generate as uuid_generate , format_uuid
from pydajet_metadata.api import APIGenerator
from pydajet_metadata.bridge import PolarsBridge
from pydajet_metadata.query import Query
from pydajet_metadata.repository import Repository
from pydajet_metadata.schema import SchemaGenerator
from pydajet_metadata.session import Session

# MetadataClient импортируется только при использовании, не здесь
# from pydajet import MetadataClient  # ← убрать

__all__ = [
    'Session',
    'Query',
    'Repository',
    'SchemaGenerator',
    'PolarsBridge',
    'APIGenerator',
    'from_1c',
    'to_1c',
    'uuid_generate',
    'format_uuid',
]
