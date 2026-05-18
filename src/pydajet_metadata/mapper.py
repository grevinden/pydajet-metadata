# src/pydajet_metadata/mapper.py
"""ColumnMapper: преобразование human ↔ db ↔ python для одной таблицы."""

from typing import Any

from sqlalchemy import LargeBinary

from pydajet_metadata._uuid import format_uuid, from_1c, to_1c


class ColumnMapper:
    """
    Маппинг имён колонок между человеческим форматом и БД.

    Отвечает ТОЛЬКО за преобразование имён и значений.
    Не зависит от Query, Session, транзакций.
    """

    def __repr__(self) -> str:
        return f"ColumnMapper(columns={len(self._column_map)})"

    def __init__(self, table, column_map: dict[str, str]):
        """
        Args:
                table: SQLAlchemy Table
                column_map: {human_name: db_name}
        """
        self._table = table
        self._column_map = column_map  # {human: db_name}
        self._reverse_map = {
            v.lower(): k for k, v in column_map.items()
        }  # {db_name_lower: human}

    def human_to_db(self, data: dict[str, Any]) -> dict[str, Any]:
        """Преобразует {human_name: value} → {db_name: value}."""
        db_data = {}
        for human_name, value in data.items():
            if human_name in self._column_map:
                db_name = self._column_map[human_name].lower()
                if isinstance(value, str) and self._is_binary(db_name):
                    try:
                        value = to_1c(value)
                    except (ValueError, AttributeError):
                        pass
                db_data[db_name] = value
            else:
                db_data[human_name.lower()] = value
        return db_data

    def db_to_human(self, row) -> dict[str, Any]:
        """Преобразует строку БД → {human_name: value}."""
        d = {}
        for col in self._table.columns:
            human_name = self._reverse_map.get(col.name.lower(), col.name)
            val = getattr(row, col.name)
            if isinstance(val, bytes) and len(val) == 16:
                val = format_uuid(from_1c(val))
            elif isinstance(val, bytes):
                val = val.hex()
            d[human_name] = val
        return d

    def get_db_column(self, human_name: str):
        """Возвращает SQLAlchemy Column по человеческому имени."""
        if human_name in self._column_map:
            db_name = self._column_map[human_name].lower()
            if db_name in self._table.c:
                return self._table.c[db_name]
        raise KeyError(f"Column '{human_name}' not found in mapping")

    @property
    def human_names(self) -> list[str]:
        """Список человеческих имён колонок."""
        return list(self._column_map.keys())

    @property
    def db_names(self) -> list[str]:
        """Список имён колонок в БД."""
        return [v.lower() for v in self._column_map.values()]

    def _is_binary(self, db_name: str) -> bool:
        """Проверяет, является ли колонка бинарной."""
        return db_name in self._table.c and isinstance(
            self._table.c[db_name].type, LargeBinary
        )
