# PyDaJet Metadata

**Python-клиент для 1С:Предприятие 8** — чтение, запись и анализ метаданных и данных напрямую из PostgreSQL и MS SQL Server.

## 📋 Содержание

- [О проекте](#о-проекте)
- [Структура](#структура)
- [Установка](#установка)
- [Быстрый старт](#быстрый-старт)
- [Модуль `pydajet`](#модуль-pydajet)
- [Модуль `pydajet_metadata`](#модуль-pydajet_metadata)
- [Протоколы](#протоколы)
- [Тестирование](#тестирование)
- [Текущее состояние](#текущее-состояние)
- [Полезные ссылки](#полезные-ссылки)

---

## О проекте

Проект разделён на два независимых слоя:

- `pydajet` — низкоуровневый доступ к DaJet Metadata через .NET Runtime и `pythonnet`
- `pydajet_metadata` — высокоуровневый Python API для работы с данными, динамическими моделями, REST и аналитикой

Основная цель: сохранить обратную совместимость, разнести метаданные и данные по слоям и сделать прикладную логику легко тестируемой.

---

## Структура

```
src/
├── pydajet/                  # Слой метаданных (.NET, pythonnet)
│   ├── __init__.py
│   ├── _platform.py
│   └── client.py
└── pydajet_metadata/         # Прикладной слой (SQLAlchemy, Pydantic, FastAPI, Polars)
    ├── __init__.py
    ├── _uuid.py
    ├── _types.py
    ├── session.py
    ├── query.py
    ├── repository.py
    ├── schema.py
    ├── bridge.py
    ├── api.py
    └── protocols.py
```

---

## Установка

### Требования

- Python ≥ 3.13
- .NET Runtime 10.0 для работы `pydajet`
- PostgreSQL ≥ 12 для работы с хранилищем данных

### Установка зависимостей

```bash
uv add pydajet-metadata
uv add --dev pytest pytest-asyncio pytest-cov pytest-mock hypothesis httpx mypy
```

---

## Быстрый старт

```python
from pydajet_metadata import Repository

repo = Repository(
    "Host=localhost;Port=5433;Database=MyBase;Username=postgres;Password=secret;"
)

query = repo.query('Справочники', 'Контрагенты')
rows = query.all()
print(rows)
```

---

## Модуль `pydajet`

`pydajet` обеспечивает низкоуровневый доступ к метаданным 1С через DaJet Metadata.

### MetadataClient

```python
from pydajet import MetadataClient

client = MetadataClient(
    "Host=localhost;Database=TestDB;Username=test;Password=test;"
)
print(client.list_types())
```

#### Основные методы

- `list_types()` — возвращает список типов метаданных (`Справочники`, `Документы`, ...)
- `list_objects(type_name)` — возвращает описания объектов выбранного типа, таблиц, реквизитов и табличных частей

#### Свойства

- `config_name` — имя конфигурации 1С
- `config_alias` — алиас конфигурации
- `platform_version` — версия платформы 1С

### UUID utilities

Утилиты для конвертации UUID между стандартным форматом и форматом 1С.

```python
from pydajet import to_1c, format_uuid

uuid_bytes = to_1c("5000289c-66b6-fadf-11f1-4e880e761abe")
print(format_uuid(uuid_bytes))
```

---

## Модуль `pydajet_metadata`

Этот слой работает с данными, SQLAlchemy, динамическими Pydantic-моделями, FastAPI и Polars.

### Repository

`Repository` объединяет метаданные и SQLAlchemy-сессию.

```python
from pydajet import MetadataClient
from pydajet_metadata import Repository, Session

client = MetadataClient("Host=localhost;Database=TestDB;Username=test;Password=test;")
session = Session("Host=localhost;Database=TestDB;Username=test;Password=test;")
repo = Repository(client=client, session=session)

print(repo.types())
print(repo.objects('Справочники'))
```

### Query

Построитель CRUD-запросов для объекта 1С.

```python
query = repo.query('Справочники', 'ирАлгоритмы')
print(query.count())
print(query.where(query.Наименование == 'telegram').all())
```

### SchemaGenerator

Генерирует Pydantic-модели на основе структуры объекта.

```python
from pydajet_metadata import SchemaGenerator

gen = SchemaGenerator(repo)
model = gen['Справочники.Контрагенты']
instance = model.from_db('9c280050-b666-dffa-11f1-4e880e761abe')
```

### APIGenerator

Генерирует REST API на FastAPI из репозитория.

```python
from pydajet_metadata import APIGenerator

app = APIGenerator(repo).generate()
app.run()
```

### PolarsBridge

Интеграция с `polars` для чтения и записи данных.

```python
from pydajet_metadata import PolarsBridge

bridge = PolarsBridge(repo)
df = bridge.read('Справочники', 'Контрагенты')
bridge.write(df, 'Справочники', 'Контрагенты')
```

---

## Протоколы

`pydajet_metadata` работает через `typing.Protocol`, чтобы отделить контракт от реализации.

### Основные интерфейсы

- `IMetadataClient` — контракт клиента метаданных
- `ISession` — контракт управления соединением и транзакциями
- `IQuery` — контракт CRUD-запросов для объекта
- `IColumnMapper` — маппинг human ↔ db
- `IRepository` — контракт репозитория

### Пример использования протоколов

```python
from unittest.mock import Mock
from pydajet_metadata import Repository
from pydajet_metadata.protocols import IMetadataClient, ISession

mock_client = Mock(spec=IMetadataClient)
mock_client.list_types.return_value = ['Справочники']
mock_client.list_objects.return_value = [
    {
        'name': 'Справочник.Контрагенты',
        'short_name': 'Контрагенты',
        'table': '_Reference123',
        'properties': [{'name': 'Ссылка', 'columns': [{'name': '_IDRRef'}]}],
        'children': [],
    }
]

mock_session = Mock(spec=ISession)
mock_session.get_pk.return_value = '_idrref'
mock_session.reflect_table.return_value = ...

repo = Repository(client=mock_client, session=mock_session)
```

---

## Тестирование

```bash
uv run pytest tests/ -q
uv run mypy src/pydajet_metadata --strict
uv run pytest tests/ --cov=src/pydajet --cov=src/pydajet_metadata --cov-report=term-missing
```

---

## Текущее состояние

- `242 passed, 2 skipped`
- `96%` покрытие по `src/pydajet` и `src/pydajet_metadata`

## Что исправлено

- Исправлена логика `Query._pk_condition` для случая отсутствующего PK-столбца
- Повышена изоляция тестов импорта `pydajet` без .NET Runtime
- Документация объединена и централизована в `README.md`

---

## Полезные ссылки

- `pyproject.toml` — зависимости и сборка
- `tests/` — тесты и фикстуры
- `src/pydajet_metadata/protocols.py` — контракты DI
- `src/pydajet_metadata/repository.py` — основной репозиторий
- `src/pydajet_metadata/query.py` — CRUD и блокировки
