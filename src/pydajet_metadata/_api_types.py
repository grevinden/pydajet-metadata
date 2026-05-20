"""Типы для FastAPI-генератора."""

from __future__ import annotations

from typing import TypedDict

from pydantic import BaseModel

from pydajet_metadata.protocols import IQuery


class ObjectRouteBundle(TypedDict):
    query: IQuery
    response: type[BaseModel]
    create: type[BaseModel]
    update: type[BaseModel]
