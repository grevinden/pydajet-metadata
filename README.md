# PyDaJet Metadata

**Python-клиент для 1С:Предприятие 8** — чтение, запись и анализ метаданных и данных напрямую из PostgreSQL и MS SQL Server.

## 📋 Содержание

- [О проекте](#о-проекте)
- [Структура](#структура)
- [Установка](#установка)
- [Быстрый старт](#быстрый-старт)
- [Модуль `pydajet`](#модуль-pydajet)
- [Модуль `pydajet_metadata`](#модуль-pydajet_metadata)
- [Асинхронный режим](#асинхронный-режим)
- [Протоколы](#протоколы)
- [API контракт](#api-контракт)
- [Тестирование](#тестирование)
- [Текущее состояние](#текущее-состояние)
- [Миграция](#миграция)
- [Полезные ссылки](#полезные-ссылки)

---

## О проекте

Проект разделён на два независимых слоя:

- `pydajet` — низкоуровневый доступ к DaJet Metadata через .NET Runtime и `pythonnet`
- `pydajet_metadata` — прикладной Python API для работы с данными, динамическими моделями, REST и аналитикой

Основная цель: разнести метаданные и данные по слоям, сохранить обратную совместимость и сделать прикладную логику легко тестируемой, в том числе через мокируемые протоколы.

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
    ├── async_session.py
    ├── query.py
    ├── async_query.py
    ├── repository.py
    ├── async_repository.py
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

#### Методы

- `list_types()` — возвращает список типов метаданных (`Справочники`, `Документы`, ...)
- `list_objects(type_name)` — возвращает описание объектов типа, таблицы, реквизиты и табличные части

#### Свойства

- `config_name` — имя текущей конфигурации 1С
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

CRUD-построитель для объекта 1С.

```python
query = repo.query('Справочники', 'ирАлгоритмы')
print(query.count())
print(query.where(query.Наименование == 'telegram').all())
```

### Асинхронный режим

`pydajet_metadata` теперь поддерживает параллельную структуру async-интерфейсов, оставляя существующий sync API неизменным.

```python
from pydajet_metadata import AsyncRepository

repo = AsyncRepository(
    connection_string="Host=localhost;Port=5433;Database=MyBase;Username=postgres;Password=secret;"
)

async def run():
    query = await repo.query('Справочники', 'Контрагенты')
    rows = await query.all()
    print(rows)
    await repo.close()
```

Дополнительно доступны:

- `AsyncSession` — async-обёртка над `Session`
- `AsyncQuery` — async-обёртка над `Query`
- `AsyncRepository` — async-обёртка над `Repository`
- `IAsyncSession`, `IAsyncQuery`, `IAsyncRepository`, `IAsyncMetadataClient` — асинхронные контракты

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

`pydajet_metadata` разделяет контракт и реализацию через `typing.Protocol`.
Это позволяет заменить реальный клиент или сессию моками и сохранить обратную совместимость.

### Основные интерфейсы

- `IMetadataClient` — контракт клиента метаданных
- `ISession` — контракт управления соединением и транзакциями
- `IQuery` — контракт CRUD-запросов
- `IColumnMapper` — контракт маппинга human ↔ db
- `IRepository` — контракт репозитория

### Преимущества

- отсутствие жёсткой привязки к `pydajet`
- тестирование через моки
- структурное соответствие без наследования протоколов
- нулевые runtime-накладные расходы для `TYPE_CHECKING`

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

## API контракт

### `MetadataClient`

| Метод | Описание | Параметры | Возвращает |
|-------|----------|-----------|------------|
| `__init__(connection_string, data_source='postgresql')` | Создаёт клиента и загружает конфигурацию 1С | `connection_string: str`, `data_source: str` | `MetadataClient` |
| `list_types()` | Возвращает список типов метаданных | без параметров | `list[str]` |
| `list_objects(type_name)` | Возвращает объекты типа | `type_name: str` | `list[dict[str, Any]]` |

### UUID utilities

| Функция | Описание | Параметры | Возвращает |
|--------|----------|-----------|------------|
| `from_1c(uuid_bytes)` | Преобразует 16 байт из формата 1С в UUID | `uuid_bytes: bytes` | `UUID` |
| `to_1c(uuid)` | Преобразует UUID, строку или байты в формат 1С | `uuid: UUID \| str \| bytes` | `bytes` |
| `generate()` | Генерирует новый UUID | без параметров | `UUID` |
| `format_uuid(uuid)` | Приводит UUID к строковому виду с дефисами | `uuid: UUID \| str \| bytes` | `str` |

---

## Тестирование

### Структура модульных тестов

```
tests/
├── unit/
│   ├── bridge/test_bridge.py
│   ├── mapper/test_mapper.py
│   ├── query/test_query_extended.py
│   ├── repository/test_repository.py
│   ├── schema/test_schema_extended.py
│   └── session/test_session_extended.py
└── conftest.py
```

### Что покрыто

- `Session`: обработка подключения, кэш рефлексии, PK fallback, транзакции и savepoint
- `Query`: чтение, запись, фильтрация, блокировки, версии, `Изменить`/`БезопасноеИзменить`
- `SchemaGenerator`: динамические Pydantic-модели, табличные части, `from_db()`, `save()`, `delete()`, `all()`
- `PolarsBridge`: чтение/запись `DataFrame`, append/replace, вложенные табличные части
- `Repository`: DI-конструктор, кэш метаданных, `types()`, `objects()`, `query()`, `refresh_metadata()`
- `ColumnMapper`: `human_to_db`, `db_to_human`, работа с бинарными типами и UUID

### Запуск

```bash
uv run pytest tests/ -q
uv run mypy src/pydajet_metadata --strict
uv run pytest tests/ --cov=src/pydajet --cov=src/pydajet_metadata --cov-report=term-missing
```

---

## Текущее состояние

- `242 passed, 2 skipped`
- `96%` покрытие по `src/pydajet` и `src/pydajet_metadata`

## Миграция

### Было

```python
from pydajet.parser import MetadataParser
from pydajet.config import ConfigReader

class Analyzer:
    def __init__(self, parser: MetadataParser, config: ConfigReader):
        ...
```

### Стало

```python
from pydajet_metadata.protocols import IMetadataClient, ISession

class Analyzer:
    def __init__(self, parser: IMetadataClient, session: ISession):
        ...
```

Протоколы описывают контракт, а не реализацию. Это упрощает подмену зависимостей и снижает область жестких связей.

---

## Полезные ссылки

- `pyproject.toml` — зависимости и сборка
- `tests/` — тесты и фикстуры
- `src/pydajet_metadata/protocols.py` — контракты DI
- `src/pydajet_metadata/repository.py` — основной репозиторий
- `src/pydajet_metadata/query.py` — CRUD и блокировки
