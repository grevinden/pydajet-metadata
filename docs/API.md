# API Documentation

## pydajet (низкоуровневый модуль)

### MetadataClient
**Описание:** клиент метаданных 1С, работающий через DaJet Metadata.
**Протокол:** `IMetadataClient`

#### Методы:
| Метод | Описание | Параметры | Возвращает |
|-------|----------|-----------|------------|
| `__init__(connection_string, data_source='postgresql')` | Создаёт клиента и загружает конфигурацию 1С. | `connection_string: str` — строка подключения PostgreSQL или SQL Server; `data_source: str` — тип источника данных. | `MetadataClient` |
| `list_types()` | Возвращает список типов метаданных (`Справочники`, `Документы`, ...). | Без параметров | `list[str]` |
| `list_objects(type_name)` | Возвращает список объектов указанного типа с описанием таблицы, свойств и табличных частей. | `type_name: str` | `list[dict[str, Any]]` |

#### Свойства:
| Свойство | Описание | Тип |
|----------|----------|-----|
| `config_name` | Имя текущей конфигурации 1С | `str` |
| `config_alias` | Алиас конфигурации, если задан | `str | None` |

**Пример использования:**
```python
from pydajet import MetadataClient

client = MetadataClient(
    "Host=localhost;Database=TestDB;Username=test;Password=test;"
)
print(client.config_name)
print(client.list_types())
``` 

### UUID utilities
**Описание:** утилиты для конвертации UUID между стандартным форматом и форматом 1С.

#### Функции:
| Функция | Описание | Параметры | Возвращает |
|--------|----------|-----------|------------|
| `from_1c(uuid_bytes)` | Преобразует 16 байт из формата 1С в UUID. | `uuid_bytes: bytes` | `UUID` |
| `to_1c(uuid)` | Преобразует UUID, строку или байты в формат 1С. | `uuid: UUID | str | bytes` | `bytes` |
| `generate()` | Генерирует новый UUID. | Без параметров | `UUID` |
| `format_uuid(uuid)` | Приводит UUID к строковому виду с дефисами. | `uuid: UUID | str | bytes` | `str` |

**Пример использования:**
```python
from pydajet import to_1c, format_uuid

uuid_bytes = to_1c("5000289c-66b6-fadf-11f1-4e880e761abe")
print(format_uuid(uuid_bytes))
```

---

## pydajet-metadata (прикладной модуль)

### Архитектурное решение
`pydajet-metadata` построен на протоколах, которые описывают только то, что реально используется.
Это позволяет:
- полностью разорвать жёсткие зависимости между `pydajet` и `pydajet-metadata`;
- легко тестировать прикладную логику моками;
- подменять клиент метаданных и соединение с базой через DI.

Вместо прямого импорта конкретного класса:
```python
from pydajet.client import MetadataClient

class Analyzer:
    def __init__(self, parser: MetadataClient):
        ...
```
используется протокол:
```python
from pydajet_metadata.protocols import IMetadataClient

class Analyzer:
    def __init__(self, parser: IMetadataClient):
        ...
```

### Протоколы

#### `IMetadataClient`
**Описание:** контракт клиента метаданных 1С.

| Метод | Описание | Параметры | Возвращает |
|-------|----------|-----------|------------|
| `list_types()` | Список типов метаданных | Без параметров | `list[str]` |
| `list_objects(type_name)` | Описание объектов типа | `type_name: str` | `list[dict[str, Any]]` |

#### `ISession`
**Описание:** контракт управления соединением и транзакциями.

| Метод/свойство | Описание | Тип |
|---------------|----------|-----|
| `engine` | SQLAlchemy Engine или активное соединение | `Any` |
| `reflect_table(table_name)` | Рефлектирует объект таблицы | `str` | `Any` |
| `get_pk(table_name)` | Возвращает PK-колонку таблицы | `str` |
| `transaction()` | Менеджер транзакций | `contextmanager` |
| `savepoint()` | Менеджер savepoint | `contextmanager` |
| `close()` | Закрывает соединение | `None` |

#### `IQuery`
**Описание:** контракт запросов к объектам 1С.

| Метод | Описание | Параметры | Возвращает |
|-------|----------|-----------|------------|
| `all()` | Возвращает все строки | Без параметров | `list[dict[str, Any]]` |
| `first()` | Возвращает первую строку | Без параметров | `dict[str, Any] | None` |
| `count()` | Количество строк | Без параметров | `int` |
| `where(*conditions)` | Применяет фильтр | `Any` | `IQuery` |
| `insert(data, extra=None)` | Вставляет запись | `dict[str, Any], dict[str, Any] | None` | `str` |
| `update(record_id, data)` | Обновляет запись | `str, dict[str, Any]` | `bool` |
| `delete(record_id)` | Удаляет запись | `str` | `bool` |
| `lock(...)` | Блокирует таблицу/строку | `...` | `None` |
| `Изменить(...)` | Обновляет с проверкой `_Version` | `...` | `bool` |
| `БезопасноеИзменить(...)` | Автоматически получает версию | `...` | `bool` |
| `ПолучитьВерсию(record_id)` | Возвращает текущую версию | `str` | `int` |

#### `IColumnMapper`
**Описание:** контракт маппинга human ↔ db.

| Метод | Описание | Параметры | Возвращает |
|-------|----------|-----------|------------|
| `human_to_db(data)` | Преобразует по-человечески именованные поля в DB | `dict[str, Any]` | `dict[str, Any]` |
| `db_to_human(row)` | Преобразует строку БД в человеческий словарь | `Any` | `dict[str, Any]` |
| `get_db_column(human_name)` | Находит SQLAlchemy Column | `str` | `Any` |

---

### Repository
**Описание:** организация доступа к объектам 1С и построение Query.
**Принимает:** `IMetadataClient` и `ISession`.

**Пример использования:**
```python
from pydajet import MetadataClient
from pydajet_metadata import Repository, Session

client = MetadataClient(
    "Host=localhost;Database=TestDB;Username=test;Password=test;"
)
session = Session(
    "Host=localhost;Database=TestDB;Username=test;Password=test;"
)
repo = Repository(client=client, session=session)
print(repo.types())
print(repo.objects('Справочники'))
query = repo.query('Справочники', 'Контрагенты')
print(query.count())
```

**Пример с mock-объектом:**
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

### Query
**Описание:** CRUD-построитель запросов для одного объекта 1С.

**Пример использования:**
```python
from pydajet_metadata import Query, Session

session = Session("Host=localhost;Database=TestDB;Username=test;Password=test;")
query = Query(session, '_Reference53', {'Ссылка': '_IDRRef', 'Наименование': '_Description'})
rows = query.all()
print(rows)
query.insert({'Наименование': 'Новый элемент'})
``` 

### SchemaGenerator
**Описание:** генерирует Pydantic-модели на основе репозитория.

**Пример использования:**
```python
from pydajet import MetadataClient
from pydajet_metadata import Repository, Session, SchemaGenerator

client = MetadataClient("Host=localhost;Database=TestDB;Username=test;Password=test;")
session = Session("Host=localhost;Database=TestDB;Username=test;Password=test;")
repo = Repository(client=client, session=session)
gen = SchemaGenerator(repo)
model = gen['Справочники.Контрагенты']
instance = model.from_db('9c280050-b666-dffa-11f1-4e880e761abe')
```

### APIGenerator
**Описание:** генерирует REST API на FastAPI по репозиторию.

**Принимает:** `IRepository`.

**Пример использования:**
```python
from pydajet_metadata import APIGenerator

api = APIGenerator(repo).generate()
api.run()
```

### PolarsBridge
**Описание:** экспортирует данные репозитория в `polars.DataFrame` и импортирует обратно.

**Пример использования:**
```python
from pydajet_metadata import PolarsBridge

bridge = PolarsBridge(repo)
df = bridge.read('Справочники', 'Контрагенты')
bridge.write(df, 'Справочники', 'Контрагенты')
```

---

## Миграция со старых версий

### Было (жёсткая связь)
```python
from pydajet.parser import MetadataParser
from pydajet.config import ConfigReader

class Analyzer:
    def __init__(self, parser: MetadataParser, config: ConfigReader):
        ...
```

### Стало (инверсия зависимости)
```python
from pydajet_metadata.protocols import IMetadataClient, ISession

class Analyzer:
    def __init__(self, parser: IMetadataClient, session: ISession):
        ...
```

### Почему протоколы
- Протоколы описывают только контракт, а не реализацию.
- Позволяют заменить реальный клиент моками и тестировать прикладной слой независимо.
- Уменьшают область жестких зависимостей и упрощают поддержку.

---

## Публичные протоколы

### `IMetadataClient`
Описывает клиента метаданных, который отдаёт типы и объекты.

### `ISession`
Описывает соединение с БД и транзакционный контекст.

### `IQuery`
Описывает CRUD-операции и работу с табличными частями.

### `IColumnMapper`
Описывает преобразование human ↔ db для одной таблицы.

### `IRepository`
Описывает репозиторий 1С с методами `types`, `objects`, `query`, `check_metadata_actual`, `refresh_metadata`.
