"""Общие фикстуры для всех тестов."""

import pytest
from datetime import datetime
from uuid import UUID
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pydajet_metadata.protocols import IRepository, ISession, IColumnMapper


@pytest.fixture
def sample_connection_string():
    return "Host=localhost;Port=5433;Database=TestDB;Username=test;Password=test;"


@pytest.fixture
def sample_uuid_bytes():
    """UUID справочника в формате 1С (перевёрнутый)."""
    return b"\x9c\x28\x00\x50\xb6\x66\xdf\xfa\x11\xf1\x4e\x88\x0e\x76\x1a\xbe"


@pytest.fixture
def sample_uuid():
    """Стандартный UUID после конвертации из 1С."""
    return UUID("5000289c-66b6-fadf-11f1-4e880e761abe")


@pytest.fixture
def sample_uuid_hex():
    """UUID без дефисов."""
    return "5000289c66b6fadf11f14e880e761abe"


@pytest.fixture
def sample_uuid_formatted():
    """UUID с дефисами."""
    return "5000289c-66b6-fadf-11f1-4e880e761abe"


@pytest.fixture
def sample_column_map():
    return {
        "Ссылка": "_IDRRef",
        "ВерсияДанных": "_Version",
        "ПометкаУдаления": "_Marked",
        "Наименование": "_Description",
        "Код": "_Code",
        "ТекстАлгоритма": "_Fld56",
        "ДатаИзменения": "_Fld57",
        "Комментарий": "_Fld58",
    }


@pytest.fixture
def sample_row_data():
    return {
        "_idrref": b"\x9c\x28\x00\x50\xb6\x66\xdf\xfa\x11\xf1\x4e\x88\x0e\x76\x1a\xbe",
        "_version": 0,
        "_marked": False,
        "_description": "Тестовый алгоритм",
        "_code": "001",
        "_fld56": 'Сообщить("Привет");',
        "_fld57": datetime(2026, 5, 13, 7, 56, 10),
        "_fld58": "Комментарий",
        "_predefinedid": b"\x00" * 16,
    }


@pytest.fixture
def mock_repository() -> "IRepository":
    """Создаёт замоканный Repository (соответствует IRepository)."""
    from unittest.mock import MagicMock

    mock = MagicMock()
    mock.types.return_value = ["Справочники", "Документы"]
    mock.objects.return_value = ["ирАлгоритмы", "ТемыУведомлений"]
    return mock


@pytest.fixture
def mock_session() -> "ISession":
    """Создаёт замоканный Session с базовой конфигурацией (соответствует ISession)."""
    from unittest.mock import MagicMock
    from sqlalchemy import MetaData, Table, Column, String

    mock = MagicMock()
    mock_table = Table('_Reference53', MetaData(), Column('_IDRRef', String))
    mock.reflect_table.return_value = mock_table
    mock.engine = MagicMock()
    return mock


@pytest.fixture
def mock_query(mock_session, sample_column_map):
    """Создаёт замоканый Query для тестов."""
    from unittest.mock import MagicMock, patch
    from pydajet_metadata.query import Query

    with patch('pydajet_metadata.query.ColumnMapper') as mock_mapper_cls:
        mock_mapper = MagicMock()
        mock_mapper.human_names = list(sample_column_map.keys())
        mock_mapper_cls.return_value = mock_mapper
        
        query = Query(
            mock_session,
            '_Reference53',
            sample_column_map,
            pk='_IDRRef',
            owner_key='_OwnerRRef'
        )
        yield query


@pytest.fixture
def mock_table_columns():
    """Фикстура с моками для колонок таблицы."""
    from unittest.mock import MagicMock
    from sqlalchemy.types import String, Integer, Boolean, DateTime, LargeBinary

    return {
        '_idrref': MagicMock(name='_IDRRef', nullable=False, type=LargeBinary),
        '_version': MagicMock(name='_Version', nullable=False, type=Integer),
        '_marked': MagicMock(name='_Marked', nullable=False, type=Boolean),
        '_description': MagicMock(name='_Description', nullable=False, type=String(150)),
        '_code': MagicMock(name='_Code', nullable=True, type=String(50)),
        '_fld56': MagicMock(name='_Fld56', nullable=True, type=String),
        '_fld57': MagicMock(name='_Fld57', nullable=True, type=DateTime),
        '_fld58': MagicMock(name='_Fld58', nullable=True, type=String),
    }


@pytest.fixture
def sample_model_data():
    """Пример данных для создания экземпляра модели."""
    return {
        'Наименование': 'Тестовый элемент',
        'Код': 'TEST001',
        'ТекстАлгоритма': 'Сообщить("Привет");',
        'ДатаИзменения': datetime(2026, 5, 18, 12, 0, 0),
        'Комментарий': 'Тестовые данные',
    }


@pytest.fixture
def sample_child_data():
    """Пример данных для табличной части."""
    return [
        {'Элемент': 'Элемент 1', 'Количество': 10},
        {'Элемент': 'Элемент 2', 'Количество': 20},
    ]


# === Фикстуры для новых модульных тестов ===
# PolarsBridge
@pytest.fixture
def mock_polars_bridge_repo() -> "IRepository":
    """Замоканный Repository для тестов PolarsBridge (соответствует IRepository)."""
    from unittest.mock import Mock
    from pydajet_metadata.protocols import IRepository
    mock = Mock(spec=IRepository)
    mock.query = Mock()
    return mock


@pytest.fixture
def polars_bridge(mock_polars_bridge_repo):
    """Экземпляр PolarsBridge с замоканым репозиторием."""
    from pydajet_metadata.bridge import PolarsBridge
    return PolarsBridge(repo=mock_polars_bridge_repo)


# Repository
@pytest.fixture
def mock_repo_metadata_client():
    """Замоканный MetadataClient для тестов Repository (соответствует IMetadataClient)."""
    from unittest.mock import Mock
    mock = Mock()
    mock.platform_version = 123
    mock.list_types.return_value = ["Catalog", "Document"]
    mock.list_objects.side_effect = lambda t: [
        {
            "short_name": "Products",
            "table": "_Reference123",
            "properties": [
                {"name": "id", "columns": [{"name": "_idrref"}]},
                {"name": "name", "columns": [{"name": "name"}]}
            ],
            "children": []
        }
    ] if t == "Catalog" else []
    return mock


@pytest.fixture
def mock_repo_session() -> "ISession":
    """Замоканный Session для тестов Repository (соответствует ISession)."""
    from unittest.mock import Mock
    from sqlalchemy import MetaData, Table, Column, String
    mock = Mock()
    mock.get_pk.return_value = "_idrref"
    table = Table('_Reference123', MetaData(), Column('_idrref', String))
    mock.reflect_table.return_value = table
    mock.engine = Mock()
    mock.close = Mock()
    return mock


# ColumnMapper
@pytest.fixture
def mapper_sample_table():
    """SQLAlchemy Table для тестов ColumnMapper."""
    from sqlalchemy import MetaData, Table, Column, String, Integer, LargeBinary
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
def mapper_sample_column_map():
    """Пример маппинга для тестов ColumnMapper."""
    return {
        "uuid": "id",
        "title": "name",
        "blob": "binary_data",
        "count": "number"
    }


@pytest.fixture
def column_mapper(mapper_sample_table, mapper_sample_column_map) -> "IColumnMapper":
    """Экземпляр ColumnMapper для тестов (соответствует IColumnMapper)."""
    from pydajet_metadata.mapper import ColumnMapper
    return ColumnMapper(table=mapper_sample_table, column_map=mapper_sample_column_map)
