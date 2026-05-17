"""
pydajet_metadata — Прикладной слой для работы с данными 1С.
"""
from pydajet_metadata._types import pg_to_sqlalchemy, sa_to_python
from pydajet_metadata.session import Session
from pydajet_metadata.query import Query
from pydajet_metadata.repository import Repository
from pydajet_metadata.schema import SchemaGenerator
from pydajet_metadata.bridge import PolarsBridge
from pydajet_metadata.api import APIGenerator

# Реэкспорт из dajet для удобства
from pydajet import MetadataClient, from_1c, to_1c, generate as uuid_generate, format_uuid

__all__ = [
    'MetadataClient',
    'Session',
    'Query',
    'Repository',
    'SchemaGenerator',
    'PolarsBridge',
    'APIGenerator',
    'from_1c', 'to_1c', 'uuid_generate', 'format_uuid',
]
