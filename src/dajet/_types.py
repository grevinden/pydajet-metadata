"""
_types.py — Маппинг типов PostgreSQL → SQLAlchemy → Python.
"""
from datetime import datetime

from sqlalchemy.types import Integer , String , Boolean , DateTime , LargeBinary , Float

PG_TO_SA = {
    'bytea': LargeBinary,
    'integer': Integer,
    'boolean': Boolean,
    'timestamp': DateTime,
    'character varying': String,
    'mvarchar': String,
    'varchar': String,
    'text': String,
    'numeric': Float,
    'bigint': Integer,
    'smallint': Integer,
    'double precision': Float,
    'real': Float,
}

SA_TO_PYTHON = {
    'string': str, 'varchar': str, 'mvarchar': str, 'text': str,
    'datetime': datetime, 'timestamp': datetime,
    'boolean': bool,
    'integer': int, 'bigint': int, 'smallint': int,
    'float': float, 'numeric': float, 'decimal': float, 'double precision': float, 'real': float,
    'bytea': bytes, 'binary': bytes, 'largebinary': bytes,
}


def pg_to_sqlalchemy(pg_type: str) -> type:
    """PostgreSQL → SQLAlchemy."""
    pg_type = pg_type.lower()
    for key, sa_type in PG_TO_SA.items():
        if key in pg_type:
            return sa_type
    return String


def sa_to_python(sa_type) -> type:
    """SQLAlchemy → Python."""
    type_str = str(sa_type).lower()
    for key, py_type in SA_TO_PYTHON.items():
        if key in type_str:
            return py_type
    return str
