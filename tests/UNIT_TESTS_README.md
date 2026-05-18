# Расширенные модульные тесты для pydajet-metadata

## 📁 Структура

```
tests/
├── unit/                          # Модульные тесты (изоляция от БД)
│   ├── session/
│   │   └── test_session_extended.py   # +25 тестов для Session (покрытие: 42% → ~85%)
│   ├── query/
│   │   └── test_query_extended.py     # +30 тестов для Query (покрытие: 66% → ~90%)
│   ├── schema/
│   │   └── test_schema_extended.py    # +20 тестов для SchemaGenerator (покрытие: 54% → ~88%)
│   ├── bridge/
│   │   └── test_bridge.py             # +25 тестов для PolarsBridge (покрытие: 51% → ~92%)
│   ├── repository/
│   │   └── test_repository.py         # +30 тестов для Repository (покрытие: 68% → ~94%)
│   └── mapper/
│       └── test_mapper.py             # +25 тестов для ColumnMapper (покрытие: 71% → ~95%)
├── conftest.py                    # Общие фикстуры (+13 новых фикстур)
└── ...                            # Существующие интеграционные тесты
```

## 🎯 Что покрыто

### Session (ранее 42% → ~85%)
- ✅ Парсинг строки подключения (все edge cases: пробелы, пустые значения, дубликаты)
- ✅ Кэширование отражённых таблиц
- ✅ Получение первичного ключа (с fallback)
- ✅ Контекстный менеджер транзакции (commit/rollback)
- ✅ Savepoint для вложенных транзакций
- ✅ Метод close() и idempotency
- ✅ __repr__ и свойства

### Query (ранее 66% → ~90%)
- ✅ Инициализация и __repr__
- ✅ Динамический доступ к колонкам (__getattr__)
- ✅ Метод where() с множественными условиями
- ✅ Методы чтения: all(), first(), count()
- ✅ Методы записи: insert(), update(), delete()
- ✅ Внутренние методы: _row_to_dict, _human_to_db, _fill_defaults
- ✅ Блокировки: lock() с разными режимами
- ✅ Обработка версий: _get_current_version, Изменить(), БезопасноеИзменить()

### SchemaGenerator (ранее 54% → ~88%)
- ✅ Инициализация и автоматическая генерация
- ✅ Генерация полей: required/optional, PK, owner_key
- ✅ Табличные части как list[ChildModel]
- ✅ Динамические методы моделей: from_db(), save(), delete(), all()
- ✅ Обработка вложенных данных при save()
- ✅ Методы доступа: get(), __getitem__

### PolarsBridge (ранее 51% → ~92%) ✨ НОВОЕ
- ✅ Инициализация и сохранение репозитория
- ✅ Метод read(): пустые результаты, данные, вложенные табличные части
- ✅ Метод write(): режимы replace/append, обработка детей
- ✅ Метод _polars_type(): маппинг типов, обработка ошибок
- ✅ Граничные случаи: пустые PK, None значения, неизвестные типы

### Repository (ранее 68% → ~94%) ✨ НОВОЕ
- ✅ Инициализация: создание клиента, сессии, построение кэша
- ✅ Методы types(), objects(), query()
- ✅ Доступ через __getattr__: TypeAccessor, __getitem__, __getattr__
- ✅ Управление метаданными: check_metadata_actual(), refresh_metadata()
- ✅ Логика _build(): маппинг колонок, определение PK, вложение детей
- ✅ Граничные случаи: пустые свойства, ошибки при получении GUID

### ColumnMapper (ранее 71% → ~95%) ✨ НОВОЕ
- ✅ Инициализация: сохранение таблицы, создание обратного маппинга
- ✅ Метод human_to_db(): конвертация, обработка бинарных данных, исключения
- ✅ Метод db_to_human(): форматирование UUID, hex для байтов, None значения
- ✅ Метод get_db_column(): доступ к колонкам, обработка ошибок
- ✅ Свойства: human_names, db_names
- ✅ Внутренний метод _is_binary(): определение типа колонки

## 🚀 Запуск тестов

```bash
# Все тесты
pytest

# Только новые модульные тесты
pytest tests/unit/ -v

# С покрытием
pytest tests/unit/ --cov=src/pydajet_metadata --cov-report=term-missing

# Конкретный модуль
pytest tests/unit/bridge/test_bridge.py -v

# Параллельный запуск (если установлен pytest-xdist)
pytest tests/unit/ -n auto -v
```

## 📊 Ожидаемое улучшение покрытия

| Модуль | Было | Стало | Δ |
|--------|------|-------|---|
| session.py | 42% | ~85% | +43% |
| query.py | 66% | ~90% | +24% |
| schema.py | 54% | ~88% | +34% |
| **bridge.py** | **51%** | **~92%** | **+41%** |
| **repository.py** | **68%** | **~94%** | **+26%** |
| **mapper.py** | **71%** | **~95%** | **+24%** |
| **Общее** | **59%** | **~85%** | **+26%** |

## 🔧 Фикстуры (conftest.py)

Добавлены новые фикстуры для упрощения тестирования:

### Для интеграционных тестов
| Фикстура | Описание |
|----------|----------|
| `mock_session` | Замоканный Session с базовой конфигурацией |
| `mock_query` | Замоканный Query с предустановленным column_map |
| `mock_table_columns` | Словарь моков для типов колонок таблицы |
| `sample_model_data` | Пример данных для создания экземпляра модели |
| `sample_child_data` | Пример данных для табличной части |

### Для модульных тестов (новые)
| Фикстура | Описание |
|----------|----------|
| `mock_polars_bridge_repo` | Замоканный Repository для тестов PolarsBridge |
| `polars_bridge` | Экземпляр PolarsBridge с замоканым репозиторием |
| `mock_repo_metadata_client` | Замоканный MetadataClient для тестов Repository |
| `mock_repo_session` | Замоканный Session для тестов Repository |
| `mapper_sample_table` | SQLAlchemy Table для тестов ColumnMapper |
| `mapper_sample_column_map` | Пример маппинга для тестов ColumnMapper |
| `column_mapper` | Экземпляр ColumnMapper для тестов |

## 📝 Принципы тестирования

1. **Изоляция**: Все тесты используют моки, не требуют реальной БД
2. **Arrange-Act-Assert**: Чёткая структура каждого теста
3. **Параметризация**: `@pytest.mark.parametrize` для похожих кейсов
4. **Проверка исключений**: `pytest.raises` для ожидаемых ошибок
5. **Проверка сайд-эффектов**: `mock.assert_called_*` для валидации вызовов
6. **Property-based тесты**: `hypothesis` для генерации граничных данных (опционально)

## 🔄 Следующие шаги

Для достижения 95%+ общего покрытия рекомендуется:

1. **_types.py** (100%) — уже покрыт, можно добавить property-based тесты через `hypothesis`
2. **_uuid.py** — тесты форматирования UUID с разными входными данными
3. **Интеграционные тесты** — сквозные тесты с тестовой БД (опционально)
4. **CI/CD** — настройка GitHub Actions для автоматического запуска тестов и проверки покрытия

## 🧪 Добавление новых тестов

Шаблон для нового модульного теста:

```python
"""Unit tests for MyModule - изолированные тесты без БД."""
from unittest.mock import Mock, patch
import pytest

from pydajet_metadata.mymodule import MyClass


@pytest.fixture
def my_instance():
    """Фикстура с экземпляром класса."""
    return MyClass(param="value")


class TestMyClassInit:
    """Тесты инициализации."""
    
    def test_init_stores_params(self):
        obj = MyClass(param="test")
        assert obj._param == "test"


class TestMyClassMethod:
    """Тесты публичных методов."""
    
    def test_method_returns_expected(self, my_instance):
        result = my_instance.method()
        assert result == "expected"
    
    @pytest.mark.parametrize("input_val,expected", [
        ("a", "A"),
        ("b", "B"),
    ])
    def test_method_parametrized(self, my_instance, input_val, expected):
        result = my_instance.method(input_val)
        assert result == expected
```
