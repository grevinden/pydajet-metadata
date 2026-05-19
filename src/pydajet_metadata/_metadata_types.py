"""Структуры метаданных 1С (ответ MetadataClient)."""

from __future__ import annotations

from typing import TypedDict


class MetadataColumn(TypedDict):
    name: str
    type: str | None


class MetadataProperty(TypedDict):
    name: str
    columns: list[MetadataColumn]


class MetadataChild(TypedDict):
    name: str
    table: str
    properties: list[MetadataProperty]


class MetadataObject(TypedDict):
    name: str
    short_name: str
    table: str
    properties: list[MetadataProperty]
    children: list[MetadataChild]
