"""Unit tests for ColumnMapper - изолированные тесты без БД."""
from unittest.mock import Mock, patch, MagicMock

import pytest
from sqlalchemy import Column, Integer, String, LargeBinary, Table, MetaData

from pydajet_metadata.mapper import ColumnMapper


@pytest.fixture
def sample_table():
    """Фикстура с примером SQLAlchemy Table."""
    metadata = MetaData()
    return Table(
        "test_table",
        metadata,
        Column("id", String(36), primary_key=True),
        Column("name", String(100)),
        Column("binary_data", LargeBinary),
        Column("number", Integer)
    )


@pytest.fixture
def sample_column_map():
    """Фикстура с примером маппинга колонок."""
    return {
        "uuid": "id",
        "title": "name",
        "blob": "binary_data",
        "count": "number"
    }


@pytest.fixture
def mapper(sample_table, sample_column_map):
    """Фикстура с экземпляром ColumnMapper."""
    return ColumnMapper(table=sample_table, column_map=sample_column_map)


class TestColumnMapperInit:
    """Тесты инициализации ColumnMapper."""

    def test_init_stores_table_and_map(self, sample_table, sample_column_map):
        """Проверка сохранения таблицы и маппинга."""
        mapper = ColumnMapper(table=sample_table, column_map=sample_column_map)
        assert mapper._table is sample_table
        assert mapper._column_map == sample_column_map

    def test_init_creates_reverse_map(self, mapper):
        """Проверка создания обратного маппинга."""
        assert mapper._reverse_map["id"] == "uuid"
        assert mapper._reverse_map["name"] == "title"
        assert mapper._reverse_map["binary_data"] == "blob"
        assert mapper._reverse_map["number"] == "count"

    def test_repr(self, mapper):
        """Проверка строкового представления."""
        assert "ColumnMapper" in repr(mapper)
        assert "columns=4" in repr(mapper)


class TestColumnMapperHumanToDb:
    """Тесты метода human_to_db()."""

    def test_convert_known_columns(self, mapper):
        """Преобразование известных колонок."""
        human_data = {"uuid": "abc123", "title": "Test"}
        db_data = mapper.human_to_db(human_data)
        
        assert db_data["id"] == "abc123"
        assert db_data["name"] == "Test"
        # Исходные ключи не должны присутствовать
        assert "uuid" not in db_data
        assert "title" not in db_data

    def test_convert_unknown_columns_pass_through(self, mapper):
        """Неизвестные колонки передаются как есть (в нижнем регистре)."""
        human_data = {"unknown_field": "value"}
        db_data = mapper.human_to_db(human_data)
        
        assert db_data["unknown_field"] == "value"

    def test_convert_mixed_columns(self, mapper):
        """Преобразование смеси известных и неизвестных колонок."""
        human_data = {"uuid": "abc", "unknown": "val", "title": "Test"}
        db_data = mapper.human_to_db(human_data)
        
        assert db_data["id"] == "abc"
        assert db_data["name"] == "Test"
        assert db_data["unknown"] == "val"

    def test_convert_binary_value_encodes(self, mapper):
        """Бинарные значения кодируются через to_1c."""
        human_data = {"blob": "hex_string"}
        
        with patch("pydajet_metadata.mapper.to_1c", return_value=b"encoded") as mock_to_1c:
            db_data = mapper.human_to_db(human_data)
            
            mock_to_1c.assert_called_once_with("hex_string")
            assert db_data["binary_data"] == b"encoded"

    def test_convert_binary_value_handles_exception(self, mapper):
        """Исключение при кодировании бинарных данных не прерывает работу."""
        human_data = {"blob": "invalid"}
        
        with patch("pydajet_metadata.mapper.to_1c", side_effect=ValueError("bad")):
            db_data = mapper.human_to_db(human_data)
            # При ошибке значение должно остаться как есть
            assert db_data["binary_data"] == "invalid"

    def test_convert_non_binary_string_not_encoded(self, mapper):
        """Небинарные строки не кодируются."""
        human_data = {"title": "Test String"}
        
        with patch("pydajet_metadata.mapper.to_1c") as mock_to_1c:
            db_data = mapper.human_to_db(human_data)
            
            mock_to_1c.assert_not_called()
            assert db_data["name"] == "Test String"


class TestColumnMapperDbToHuman:
    """Тесты метода db_to_human()."""

    def test_convert_row_to_human(self, mapper):
        """Преобразование строки БД в человеческий формат."""
        # Создаем мок строки с атрибутами
        db_row = Mock()
        db_row.id = "abc123"
        db_row.name = "Test"
        db_row.binary_data = None
        db_row.number = 42
        
        human_data = mapper.db_to_human(db_row)
        
        assert human_data["uuid"] == "abc123"
        assert human_data["title"] == "Test"
        assert human_data["count"] == 42

    def test_convert_uuid_bytes_formats(self, mapper):
        """UUID в байтах форматируется в строку."""
        db_row = Mock()
        # 16-байтовый UUID
        db_row.id = b"0123456789abcdef"
        db_row.name = "Test"
        db_row.binary_data = None
        db_row.number = 1
        
        with patch("pydajet_metadata.mapper.from_1c", return_value="formatted-uuid") as mock_from_1c:
            with patch("pydajet_metadata.mapper.format_uuid", return_value="final-uuid") as mock_format:
                human_data = mapper.db_to_human(db_row)
                
                mock_from_1c.assert_called_once_with(b"0123456789abcdef")
                mock_format.assert_called_once_with("formatted-uuid")
                assert human_data["uuid"] == "final-uuid"

    def test_convert_non_uuid_bytes_hexes(self, mapper):
        """Не-UUID байты конвертируются в hex."""
        db_row = Mock()
        db_row.id = "normal"
        db_row.name = "Test"
        # 10 байт (не 16) - не UUID
        db_row.binary_data = b"\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a"
        db_row.number = 1
        
        human_data = mapper.db_to_human(db_row)
        
        assert human_data["blob"] == "0102030405060708090a"

    def test_convert_none_values(self, mapper):
        """None значения передаются как есть."""
        db_row = Mock()
        db_row.id = None
        db_row.name = None
        db_row.binary_data = None
        db_row.number = None
        
        human_data = mapper.db_to_human(db_row)
        
        assert human_data["uuid"] is None
        assert human_data["title"] is None
        assert human_data["count"] is None

    def test_convert_columns_not_in_map_use_db_name(self, mapper):
        """Колонки не в маппинге используют имя из БД."""
        # Добавляем колонку не в маппинге
        extra_col = Column("extra_col", String)
        mapper._table.append_column(extra_col)
        
        db_row = Mock()
        db_row.id = "abc"
        db_row.extra_col = "extra_value"
        
        human_data = mapper.db_to_human(db_row)
        
        # extra_col не в маппинге, поэтому используется как есть
        assert human_data["extra_col"] == "extra_value"


class TestColumnMapperGetDbColumn:
    """Тесты метода get_db_column()."""

    def test_get_known_column(self, mapper, sample_table):
        """Получение известной колонки."""
        col = mapper.get_db_column("uuid")
        assert col is sample_table.c.id

    def test_get_unknown_column_raises(self, mapper):
        """Запрос неизвестной колонки вызывает KeyError."""
        with pytest.raises(KeyError, match="Column 'missing' not found in mapping"):
            mapper.get_db_column("missing")

    def test_get_column_db_name_not_in_table_raises(self, mapper):
        """Если db_name не в таблице, вызывается ошибка."""
        # Создаем маппинг с несуществующей колонкой
        bad_map = {"test": "nonexistent_col"}
        bad_mapper = ColumnMapper(table=mapper._table, column_map=bad_map)
        
        with pytest.raises(KeyError):
            bad_mapper.get_db_column("test")


class TestColumnMapperProperties:
    """Тесты свойств human_names и db_names."""

    def test_human_names_property(self, mapper, sample_column_map):
        """Свойство human_names возвращает список человеческих имён."""
        assert mapper.human_names == list(sample_column_map.keys())

    def test_db_names_property(self, mapper, sample_column_map):
        """Свойство db_names возвращает список имён БД в нижнем регистре."""
        expected = [v.lower() for v in sample_column_map.values()]
        assert mapper.db_names == expected


class TestColumnMapperIsBinary:
    """Тесты метода _is_binary()."""

    def test_is_binary_true_for_largebinary(self, mapper):
        """_is_binary возвращает True для LargeBinary колонок."""
        assert mapper._is_binary("binary_data") is True

    def test_is_binary_false_for_other_types(self, mapper):
        """_is_binary возвращает False для других типов."""
        assert mapper._is_binary("id") is False
        assert mapper._is_binary("name") is False
        assert mapper._is_binary("number") is False

    def test_is_binary_unknown_column_false(self, mapper):
        """_is_binary для неизвестной колонки возвращает False."""
        assert mapper._is_binary("unknown") is False


class TestColumnMapperEdgeCases:
    """Тесты граничных случаев."""

    def test_human_to_db_empty_dict(self, mapper):
        """Преобразование пустого словаря."""
        result = mapper.human_to_db({})
        assert result == {}

    def test_db_to_human_with_extra_table_columns(self, mapper):
        """db_to_human обрабатывает дополнительные колонки в таблице."""
        # Добавляем колонку в таблицу, но не в маппинг
        extra = Column("extra", String)
        mapper._table.append_column(extra)
        
        db_row = Mock()
        db_row.id = "abc"
        db_row.extra = "extra_val"
        
        result = mapper.db_to_human(db_row)
        assert "extra" in result
        assert result["extra"] == "extra_val"

    def test_column_map_case_sensitivity(self, mapper):
        """Маппинг чувствителен к регистру человеческих имён."""
        # "UUID" != "uuid" в человеческом формате
        human_data = {"UUID": "test"}  # Заглавные
        db_data = mapper.human_to_db(human_data)
        
        # Не должно быть сконвертировано, т.к. "UUID" не в маппинге
        assert "UUID" in db_data
        assert "id" not in db_data

    def test_reverse_map_case_insensitive(self, mapper):
        """Обратный маппинг нечувствителен к регистру имён БД."""
        # db_name в нижнем регистре
        assert mapper._reverse_map["ID".lower()] == "uuid"
        assert mapper._reverse_map["NAME".lower()] == "title"

    def test_empty_column_map(self, sample_table):
        """Работа с пустым маппингом."""
        mapper = ColumnMapper(table=sample_table, column_map={})
        
        # human_to_db должен передавать всё как есть
        assert mapper.human_to_db({"any": "value"}) == {"any": "value"}
        
        # db_to_human должен использовать имена из таблицы
        db_row = Mock()
        db_row.id = "abc"
        result = mapper.db_to_human(db_row)
        assert result["id"] == "abc"  # Используется имя из БД
