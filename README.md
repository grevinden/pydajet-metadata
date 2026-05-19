# PyDaJet Metadata

**Python-клиент для 1С:Предприятие 8** — чтение, запись, анализ метаданных и данных напрямую из PostgreSQL и MS SQL Server.

## 📌 О проекте

`pydajet-metadata` состоит из двух слоёв:

- `pydajet` — низкоуровневый доступ к DaJet Metadata через .NET Runtime
- `pydajet_metadata` — высокоуровневый Python API для работы с данными, динамическими моделями и REST

Главная идея: разделить метаданные и данные, сохранить обратную совместимость и сделать `pydajet_metadata` легко тестируемым.

## 🚀 Ключевые преимущества

- **Protocol-based architecture**: зависимости инвертированы через `typing.Protocol`
- **Lazy .NET loading**: `.NET Runtime` подключается только при создании `MetadataClient`
- **Dynamic Pydantic models**: `SchemaGenerator` строит модели на основе метаданных 1С
- **FastAPI генерация**: `APIGenerator` создаёт REST API из репозитория
- **DataFrame интеграция**: `PolarsBridge` работает с `polars.DataFrame`
- **Высокое покрытие тестами**: полный набор тестов и CI-ready конфигурация

## 📂 Структура проекта

```
src/
├── pydajet/                  # Слой метаданных (.NET / pythonnet)
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
    └── api.py
```

## 📦 Установка

### Требования

- Python ≥ 3.13
- .NET Runtime 10.0 для работы `pydajet`
- PostgreSQL ≥ 12 для работы с хранилищем данных

### Установка зависимостей

```bash
uv add pydajet-metadata
uv add --dev pytest pytest-asyncio pytest-cov pytest-mock hypothesis httpx mypy
```

## ⚙️ Быстрый старт

### Подключение к базе

```python
from pydajet_metadata import Repository

repo = Repository(
    "Host=localhost;Port=5433;Database=MyBase;Username=postgres;Password=secret;"
)
```

### Построение запроса

```python
query = repo.query('Справочники', 'Контрагенты')
rows = query.all()
print(rows)
```

## 🧩 Архитектура

### Два независимых слоя

- `pydajet` — работает с DaJet Metadata и .NET Runtime
- `pydajet_metadata` — работает с данными, моделями и REST API

### Protocol-based Dependency Injection

`pydajet_metadata` опирается на протоколы вместо прямых классов.
Это позволяет использовать любые реализации, не привязываясь к конкретному клиенту или сессии.

```python
from pydajet_metadata import Repository

repo = Repository(
    client=FakeMetadataClient(),
    session=FakeSession(),
)
```

## 🔧 Основные компоненты

### `pydajet`

#### `MetadataClient`

Низкоуровневый клиент для чтения метаданных из 1С через DaJet Metadata.

```python
from pydajet import MetadataClient

client = MetadataClient(
    "Host=localhost;Database=TestDB;Username=test;Password=test;"
)
print(client.list_types())
```

#### UUID utilities

Конвертация между стандартным UUID и форматом 1С.

```python
from pydajet import to_1c, format_uuid

uuid_bytes = to_1c("5000289c-66b6-fadf-11f1-4e880e761abe")
print(format_uuid(uuid_bytes))
```

### `pydajet_metadata`

#### `Repository`

Объединяет метаданные и SQLAlchemy-сессию, предоставляя простой API для доступа к объектам 1С.

```python
from pydajet import MetadataClient
from pydajet_metadata import Repository, Session

client = MetadataClient("Host=localhost;Database=TestDB;Username=test;Password=test;")
session = Session("Host=localhost;Database=TestDB;Username=test;Password=test;")
repo = Repository(client=client, session=session)

print(repo.types())
print(repo.objects('Справочники'))
```

#### `Query`

CRUD-построитель для объекта 1С.

```python
query = repo.query('Справочники', 'ирАлгоритмы')
print(query.count())
print(query.where(query.Наименование == 'telegram').all())
```

#### `SchemaGenerator`

Генерирует Pydantic-модель на основе структуры объекта 1С.

```python
from pydajet_metadata import SchemaGenerator

gen = SchemaGenerator(repo)
model = gen['Справочники.Контрагенты']
instance = model.from_db('9c280050-b666-dffa-11f1-4e880e761abe')
```

#### `APIGenerator`

Создаёт FastAPI-приложение из репозитория.

```python
from pydajet_metadata import APIGenerator

app = APIGenerator(repo).generate()
app.run()
```

#### `PolarsBridge`

Интеграция `polars` для чтения и записи данных.

```python
from pydajet_metadata import PolarsBridge

bridge = PolarsBridge(repo)
df = bridge.read('Справочники', 'Контрагенты')
bridge.write(df, 'Справочники', 'Контрагенты')
```

## 🧠 Протоколы

Протоколы описывают необходимые методы и свойства, не навязывая конкретную реализацию.

### Основные интерфейсы

- `IMetadataClient` — контракт клиента метаданных
- `ISession` — контракт управления подключением и транзакциями
- `IQuery` — контракт CRUD-запросов для объекта
- `IColumnMapper` — маппинг human ↔ db
- `IRepository` — репозиторий для прикладного слоя

### Пример использования протоколов в тестах

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

## 🧪 Тестирование

Запуск всех тестов:

```bash
uv run pytest tests/ -q
```

Покрытие и статический анализ:

```bash
uv run mypy src/pydajet_metadata --strict
uv run pytest tests/ --cov=src/pydajet --cov=src/pydajet_metadata --cov-report=term-missing
```

## ✅ Проверка

На текущий момент весь тестовый пакет проходит успешно: `242 passed, 2 skipped`.

## 📌 Что исправлено в этой версии

- Исправлена логика `Query._pk_condition` для случая отсутствующего PK-столбца
- Повышена изоляция тестов импорта `pydajet` без .NET Runtime
- Объединена и обновлена документация в `README.md`

---

## Полезные ссылки

- `pyproject.toml` — описание зависимостей и конфигурации
- `tests/` — все тесты и фикстуры
- `src/pydajet_metadata/protocols.py` — контракты для DI
- `src/pydajet_metadata/repository.py` — центральный репозиторий
- `src/pydajet_metadata/query.py` — реализация CRUD и блокировок
