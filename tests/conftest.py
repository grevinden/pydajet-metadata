"""Общие фикстуры для всех тестов."""
import pytest
from datetime import datetime
from uuid import UUID


@pytest.fixture
def sample_connection_string():
    return "Host=localhost;Port=5433;Database=TestDB;Username=test;Password=test;"


@pytest.fixture
def sample_uuid_bytes():
    """UUID справочника в формате 1С (перевёрнутый)."""
    return b'\x9c\x28\x00\x50\xb6\x66\xdf\xfa\x11\xf1\x4e\x88\x0e\x76\x1a\xbe'

@pytest.fixture
def sample_uuid():
    """Стандартный UUID после конвертации из 1С."""
    return UUID('5000289c-66b6-fadf-11f1-4e880e761abe')

@pytest.fixture
def sample_uuid_hex():
    """UUID без дефисов."""
    return '5000289c66b6fadf11f14e880e761abe'

@pytest.fixture
def sample_uuid_formatted():
    """UUID с дефисами."""
    return '5000289c-66b6-fadf-11f1-4e880e761abe'


@pytest.fixture
def sample_column_map():
    return {
        'Ссылка': '_IDRRef',
        'ВерсияДанных': '_Version',
        'ПометкаУдаления': '_Marked',
        'Наименование': '_Description',
        'Код': '_Code',
        'ТекстАлгоритма': '_Fld56',
        'ДатаИзменения': '_Fld57',
        'Комментарий': '_Fld58',
    }


@pytest.fixture
def sample_row_data():
    return {
        '_idrref': b'\x9c\x28\x00\x50\xb6\x66\xdf\xfa\x11\xf1\x4e\x88\x0e\x76\x1a\xbe',
        '_version': 0,
        '_marked': False,
        '_description': 'Тестовый алгоритм',
        '_code': '001',
        '_fld56': 'Сообщить("Привет");',
        '_fld57': datetime(2026, 5, 13, 7, 56, 10),
        '_fld58': 'Комментарий',
        '_predefinedid': b'\x00' * 16,
    }
