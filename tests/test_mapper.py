# tests/test_mapper.py — новый файл
"""Тесты ColumnMapper."""

import pytest
from sqlalchemy import Table, Column, MetaData
from sqlalchemy.types import Integer, String, LargeBinary, DateTime
from datetime import datetime

from pydajet_metadata.mapper import ColumnMapper


class TestColumnMapper:
    """Тесты ColumnMapper."""

    @pytest.fixture
    def mock_table(self):
        metadata = MetaData()
        return Table(
            "_test",
            metadata,
            Column("_idrref", LargeBinary),
            Column("_description", String),
            Column("_code", String),
            Column("_date", DateTime),
            Column("_version", Integer),
        )

    @pytest.fixture
    def mapper(self, mock_table):
        column_map = {
            "Ссылка": "_IDRRef",
            "Наименование": "_Description",
            "Код": "_Code",
            "Дата": "_Date",
            "Версия": "_Version",
        }
        return ColumnMapper(mock_table, column_map)

    def test_human_to_db_simple(self, mapper):
        """Простое преобразование human → db."""
        data = {
            "Наименование": "Тест",
            "Код": "001",
            "Дата": datetime(2026, 5, 13),
        }
        result = mapper.human_to_db(data)
        assert result["_description"] == "Тест"
        assert result["_code"] == "001"
        assert result["_date"] == datetime(2026, 5, 13)

    def test_human_to_db_with_uuid(self, mapper):
        """Преобразование с UUID-строкой."""
        data = {
            "Ссылка": "9c280050-b666-dffa-11f1-4e880e761abe",
        }
        result = mapper.human_to_db(data)
        assert "_idrref" in result
        assert len(result["_idrref"]) == 16  # bytes

    def test_human_to_db_unknown_column(self, mapper):
        """Неизвестная колонка передаётся как есть (в нижнем регистре)."""
        data = {"НеизвестнаяКолонка": "значение"}
        result = mapper.human_to_db(data)
        assert result["неизвестнаяколонка"] == "значение"

    def test_get_db_column(self, mapper):
        """Получение SQLAlchemy Column по человеческому имени."""
        col = mapper.get_db_column("Наименование")
        assert col.name == "_description"

    def test_get_db_column_not_found(self, mapper):
        """Ошибка при запросе несуществующей колонки."""
        with pytest.raises(KeyError):
            mapper.get_db_column("Несуществующая")

    def test_human_names(self, mapper):
        """Список человеческих имён."""
        names = mapper.human_names
        assert "Наименование" in names
        assert "Код" in names
        assert "Ссылка" in names

    def test_db_names(self, mapper):
        """Список имён колонок в БД."""
        names = mapper.db_names
        assert "_description" in names
        assert "_code" in names
        assert "_idrref" in names
