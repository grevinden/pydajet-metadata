"""Типы SQLAlchemy, используемые в pydajet_metadata."""

from __future__ import annotations

from typing import TypeAlias

from sqlalchemy.engine import Engine as SaEngine
from sqlalchemy.engine import RowMapping
from sqlalchemy.sql.base import Executable
from sqlalchemy.sql.elements import ColumnElement, TextClause
from sqlalchemy.sql.schema import Column, Table

Engine: TypeAlias = SaEngine
SqlExecutable: TypeAlias = Executable
SqlWhereClause: TypeAlias = ColumnElement[bool]
SqlColumn: TypeAlias = Column[object]
SqlPkColumn: TypeAlias = Column[object] | TextClause
SqlPkCondition: TypeAlias = ColumnElement[bool] | TextClause
DbRow: TypeAlias = RowMapping
