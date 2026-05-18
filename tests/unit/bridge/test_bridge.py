"""Unit tests for PolarsBridge - изолированные тесты без БД."""
from unittest.mock import MagicMock, Mock, patch

import polars as pl
import pytest

from pydajet_metadata.bridge import PolarsBridge
from pydajet_metadata.repository import Repository


@pytest.fixture
def mock_repository():
    """Фикстура с замоканым репозиторием."""
    repo = Mock(spec=Repository)
    repo.query = Mock()
    return repo


@pytest.fixture
def bridge(mock_repository):
    """Фикстура с экземпляром PolarsBridge."""
    return PolarsBridge(repo=mock_repository)


class TestPolarsBridgeInit:
    """Тесты инициализации PolarsBridge."""

    def test_init_stores_repository(self, mock_repository):
        """Проверка сохранения репозитория."""
        bridge = PolarsBridge(repo=mock_repository)
        assert bridge._repo is mock_repository


class TestPolarsBridgeRead:
    """Тесты метода read()."""

    def test_read_empty_result_returns_empty_dataframe_with_schema(self, bridge, mock_repository):
        """Чтение пустого результата возвращает пустой DataFrame со схемой."""
        mock_query = Mock()
        mock_query.all.return_value = []
        mock_query._column_map = {"id": "id", "name": "name"}
        mock_query._children = {}
        
        # Мокаем _polars_type для возврата конкретных типов
        bridge._polars_type = Mock(side_effect=lambda q, c: pl.Utf8 if c == "name" else pl.Int64)
        
        mock_repository.query.return_value = mock_query
        
        df = bridge.read("Catalog", "Products")
        
        assert isinstance(df, pl.DataFrame)
        assert df.height == 0
        assert "id" in df.columns
        assert "name" in df.columns
        mock_repository.query.assert_called_once_with("Catalog", "Products")
        mock_query.all.assert_called_once()

    def test_read_with_rows_returns_dataframe(self, bridge, mock_repository):
        """Чтение с данными возвращает DataFrame с строками."""
        mock_query = Mock()
        mock_query.all.return_value = [
            {"Ссылка": "001", "name": "Product1"},
            {"Ссылка": "002", "name": "Product2"}
        ]
        mock_query._column_map = {"Ссылка": "_idrref", "name": "name"}
        mock_query._children = {}
        
        mock_repository.query.return_value = mock_query
        
        df = bridge.read("Catalog", "Products")
        
        assert isinstance(df, pl.DataFrame)
        assert df.height == 2
        assert df["name"].to_list() == ["Product1", "Product2"]

    def test_read_with_children_nests_data(self, bridge, mock_repository):
        """Чтение с табличными частями вкладывает данные."""
        # Основной запрос
        mock_query = Mock()
        mock_query.all.return_value = [{"Ссылка": "001", "name": "Product1"}]
        mock_query._column_map = {"Ссылка": "_idrref", "name": "name"}
        mock_query._owner_key = "_idrref"
        
        # Дочерний запрос
        mock_child = Mock()
        mock_child.all.return_value = [
            {"_idrref": "c1", "_idrref_owner": "001", "value": 100},
            {"_idrref": "c2", "_idrref_owner": "001", "value": 200}
        ]
        mock_child._column_map = {"_idrref": "_idrref", "value": "value"}
        mock_child._owner_key = "_idrref_owner"
        
        mock_query._children = {"tabular_part": mock_child}
        mock_repository.query.return_value = mock_query
        
        df = bridge.read("Catalog", "Products")
        
        assert df.height == 1
        # Проверяем, что табличная часть добавлена как список
        assert "tabular_part" in df.columns
        # Polars возвращает Series при индексации list-колонки, используем .to_list()
        nested = df["tabular_part"].to_list()[0]
        assert isinstance(nested, list)
        assert len(nested) == 2
        assert nested[0]["value"] == 100

    def test_read_child_without_owner_key_skips_nesting(self, bridge, mock_repository):
        """Если у дочерней строки нет ключа владельца, она не вкладывается."""
        mock_query = Mock()
        mock_query.all.return_value = [{"Ссылка": "001"}]
        mock_query._column_map = {"Ссылка": "_idrref"}
        
        mock_child = Mock()
        # Строка без владельца
        mock_child.all.return_value = [{"_idrref": "c1", "value": 100}]
        mock_child._owner_key = "_idrref_owner"  # Ключ владельца, которого нет в данных
        
        mock_query._children = {"tabular_part": mock_child}
        mock_repository.query.return_value = mock_query
        
        df = bridge.read("Catalog", "Products")
        
        # Проверяем, что поле есть, но пустое
        assert "tabular_part" in df.columns
        assert df["tabular_part"].to_list()[0] == []


class TestPolarsBridgeWrite:
    """Тесты метода write()."""

    @pytest.mark.parametrize("mode", ["replace", "append"])
    def test_write_modes(self, bridge, mock_repository, mode):
        """Проверка режимов записи."""
        mock_query = Mock()
        mock_query.all.return_value = [] if mode == "append" else [{"Ссылка": "001"}]
        mock_query._children = {}
        mock_query.insert = Mock()
        mock_query.delete = Mock()
        
        mock_repository.query.return_value = mock_query
        
        df = pl.DataFrame({"name": ["A", "B"]})
        count = bridge.write(df, "Catalog", "Products", mode=mode)
        
        assert count == 2
        if mode == "replace":
            mock_query.delete.assert_called()
        else:
            mock_query.delete.assert_not_called()
        assert mock_query.insert.call_count == 2

    def test_write_with_children_propagates_owner_key(self, bridge, mock_repository):
        """Запись с табличными частями проставляет ключ владельца."""
        mock_query = Mock()
        mock_query.all.return_value = []
        mock_query._children = {"tabular_part": Mock()}
        mock_query.insert = Mock()
        mock_query._column_map = {}
        
        child_query = mock_query._children["tabular_part"]
        child_query._owner_key = "_idrref_owner"
        child_query.insert = Mock()
        
        mock_repository.query.return_value = mock_query
        
        df = pl.DataFrame({
            "name": ["Product1"],
            "tabular_part": [[{"value": 100}, {"value": 200}]]
        })
        
        bridge.write(df, "Catalog", "Products")
        
        # Проверяем, что insert вызван для родительской строки
        mock_query.insert.assert_called()
        # Проверяем, что для дочерних строк установлен ключ владельца
        child_query.insert.assert_called()
        call_args = child_query.insert.call_args[0][0]
        assert call_args.get("_idrref_owner") == mock_query.insert.return_value
        
        mock_repository.query.return_value = mock_query
        
        df = pl.DataFrame({"name": ["A", "B", "C"]})
        count = bridge.write(df, "Catalog", "Products")
        
        assert count == 3


class TestPolarsBridgePolarsType:
    """Тесты метода _polars_type()."""

    @pytest.mark.parametrize("py_type, expected_polars_type", [
        (str, pl.Utf8),
        (int, pl.Int64),
        (float, pl.Float64),
        (bool, pl.Boolean),
    ])
    def test_polars_type_mapping(self, bridge, mock_repository, py_type, expected_polars_type):
        """Проверка маппинга типов Python → Polars."""
        from datetime import datetime
        
        mock_query = Mock()
        mock_col = Mock()
        mock_col.type = Mock()
        
        # Мокаем sa_to_python
        with patch("pydajet_metadata.bridge.sa_to_python", return_value=py_type):
            mock_query._table.c = {"test_col": mock_col}
            mock_query._column_map = {"human": "test_col"}
            
            result = bridge._polars_type(mock_query, "human")
            assert result == expected_polars_type

    def test_polars_type_datetime(self, bridge, mock_repository):
        """Проверка маппинга datetime."""
        from datetime import datetime
        
        mock_query = Mock()
        mock_col = Mock()
        mock_col.type = Mock()
        
        with patch("pydajet_metadata.bridge.sa_to_python", return_value=datetime):
            mock_query._table.c = {"test_col": mock_col}
            mock_query._column_map = {"human": "test_col"}
            
            result = bridge._polars_type(mock_query, "human")
            assert result == pl.Datetime

    def test_polars_type_unknown_defaults_to_utf8(self, bridge, mock_repository):
        """Неизвестный тип маппится в Utf8 по умолчанию."""
        mock_query = Mock()
        mock_col = Mock()
        mock_col.type = Mock()
        
        with patch("pydajet_metadata.bridge.sa_to_python", return_value=object):
            mock_query._table.c = {"test_col": mock_col}
            mock_query._column_map = {"human": "test_col"}
            
            result = bridge._polars_type(mock_query, "human")
            assert result == pl.Utf8

    def test_polars_type_column_not_found_raises(self, bridge, mock_repository):
        """Отсутствие колонки в таблице вызывает ошибку."""
        mock_query = Mock()
        mock_query._table.c = {}  # Пустая таблица
        mock_query._column_map = {"human": "missing_col"}
        
        with pytest.raises(KeyError):
            bridge._polars_type(mock_query, "human")


class TestPolarsBridgeEdgeCases:
    """Тесты граничных случаев."""

    def test_read_with_none_pk_in_rows(self, bridge, mock_repository):
        """Строки без Ссылка не получают вложенные данные."""
        mock_query = Mock()
        mock_query.all.return_value = [{"name": "NoPK"}]  # Нет Ссылка
        mock_query._column_map = {"name": "name"}
        
        mock_child = Mock()
        mock_child.all.return_value = [{"_idrref": "c1", "_idrref_owner": "001"}]
        mock_child._owner_key = "_idrref_owner"
        
        mock_query._children = {"tabular_part": mock_child}
        mock_repository.query.return_value = mock_query
        
        df = bridge.read("Catalog", "Products")
        
        # Проверяем, что для строки без Ссылка вложенные данные пусты
        assert df["tabular_part"].to_list()[0] == []

    def test_write_with_empty_dataframe(self, bridge, mock_repository):
        """Запись пустого DataFrame не вызывает insert."""
        mock_query = Mock()
        mock_query.all.return_value = []
        mock_query._children = {}
        mock_query.insert = Mock()
        
        mock_repository.query.return_value = mock_query
        
        df = pl.DataFrame(schema={"name": pl.Utf8})  # Пустой, но со схемой
        count = bridge.write(df, "Catalog", "Products")
        
        assert count == 0
        mock_query.insert.assert_not_called()

    def test_write_removes_child_keys_from_parent_row(self, bridge, mock_repository):
        """При записи ключи табличных частей удаляются из родительской строки."""
        mock_query = Mock()
        mock_query.all.return_value = []
        mock_query._children = {"tabular_part": Mock()}
        mock_query.insert = Mock()
        
        mock_repository.query.return_value = mock_query
        
        df = pl.DataFrame({
            "name": ["Product1"],
            "tabular_part": [[{"value": 100}]]
        })
        
        bridge.write(df, "Catalog", "Products")
        
        # Проверяем, что insert вызван с данными без ключа табличной части
        call_args = mock_query.insert.call_args[0][0]
        assert "tabular_part" not in call_args
        assert "name" in call_args
