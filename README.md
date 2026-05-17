# PyDaJet Metadata

**Python-клиент для 1С:Предприятие 8** — чтение, запись, анализ метаданных и данных напрямую из PostgreSQL и MS SQL Server.

## 📋 Содержание

1. [Архитектура проекта](#архитектура-проекта)
2. [Установка](#установка)
3. [Подключение к базе](#подключение-к-базе)
4. [Слой метаданных (pydajet)](#слой-метаданных-pydajet)
5. [Слой данных (pydajet_metadata)](#слой-данных-pydajet_metadata)
6. [ORM-интерфейс (Repository)](#orm-интерфейс-repository)
7. [Генератор API (FastAPI)](#генератор-api-fastapi)
8. [Polars-интеграция](#polars-интеграция)
9. [Динамические Pydantic-модели](#динамические-pydantic-модели)
10. [Транзакции и блокировки](#транзакции-и-блокировки)
11. [UUID-конвертация](#uuid-конвертация)
12. [Тестирование](#тестирование)

---

## Архитектура проекта

Проект разделён на два независимых слоя:

```
src/
├── pydajet/                          # Слой метаданных (взаимодействие с .NET)
│   ├── __init__.py                   # Инициализация .NET Runtime
│   ├── _platform.py                  # Поиск бинарников для текущей ОС
│   └── client.py                     # Низкоуровневый доступ к метаданным 1С
│
└── pydajet_metadata/                 # Прикладной слой (работа с данными)
    ├── __init__.py                   # Реэкспорт основных классов
    ├── _uuid.py                      # Конвертация UUID 1С ↔ стандартный
    ├── _types.py                     # Маппинг типов PostgreSQL → SQLAlchemy → Python
    ├── session.py                    # Подключение к БД и транзакции
    ├── query.py                      # Query builder (чтение/запись/блокировки)
    ├── repository.py                 # Репозиторий (объединяет метаданные + запросы)
    ├── schema.py                     # Генератор динамических Pydantic-моделей
    ├── bridge.py                     # Polars-интеграция
    └── api.py                        # FastAPI/OpenAPI-генератор
```

### Принцип разделения

| Слой | Назначение | Зависимости |
|------|-----------|-------------|
| `pydajet` | Низкоуровневый доступ к API DaJet Metadata через .NET Runtime | .NET Runtime, pythonnet |
| `pydajet_metadata` | Высокоуровневый интерфейс для работы с данными | SQLAlchemy, Polars, FastAPI |

Слой `pydajet_metadata` **не требует .NET Runtime** для импорта — он загружается лениво только при создании экземпляра `MetadataClient`. Это позволяет запускать тесты и использовать вспомогательные функции без установленного .NET.

---

## Установка

### Требования

| Компонент | Версия |
|-----------|--------|
| Python | ≥ 3.13 |
| .NET Runtime | 10.0 (для работы с метаданными) |
| PostgreSQL | ≥ 12 (для работы с данными) |

### Установка пакета

```bash
# Основные зависимости
uv add pydajet-metadata

# Для разработки (тесты, линтеры)
uv add --dev pytest pytest-asyncio pytest-cov pytest-mock hypothesis httpx
```

### Структура установленного пакета

```
site-packages/
├── pydajet/                    # Слой метаданных
│   ├── __init__.py
│   ├── _platform.py
│   └── client.py
├── pydajet_metadata/           # Прикладной слой
│   ├── __init__.py
│   ├── _uuid.py
│   ├── _types.py
│   ├── session.py
│   ├── query.py
│   ├── repository.py
│   ├── schema.py
│   ├── bridge.py
│   ├── api.py
│   └── bin/                    # Бинарники .NET (автоматически загружаются)
│       ├── win-x64/
│       ├── linux-x64/
│       └── ...
└── dajet/                      # Алиас для удобного импорта
    └── __init__.py
```

---

## Подключение к базе

### Строка подключения

Формат строки подключения совместим с 1С:

```
Host=localhost;Port=5433;Database=MyBase;Username=postgres;Password=secret;
```

### Создание репозитория

```python
from pydajet_metadata import Repository

# PostgreSQL
repo = Repository(
    "Host=localhost;Port=5433;Database=vbncvbncv;Username=vbnvbn;Password=cvbbc;"
)

# MS SQL Server
repo = Repository(
    "Server=localhost;Database=MyBase;User Id=sa;Password=secret;",
    data_source="sqlserver"
)
```

### Просмотр структуры базы

```python
# Все типы объектов
print(repo.types())
# ['Документы', 'Константы', 'Перечисления', 'РегистрыСведений', 'Справочники', ...]

# Все объекты типа
print(repo.Справочники.все())
# ['ирАлгоритмы', 'ирОбъектыДляОтладки', 'ТемыУведомлений', ...]

# Все объекты всех типов
print(repo.объекты)
# {'Справочники': ['ирАлгоритмы', ...], 'Документы': ['Уведомления', ...], ...}
```

---

## Слой метаданных (pydajet)

### MetadataClient

Низкоуровневый клиент для чтения метаданных 1С через .NET Runtime.

```python
from pydajet import MetadataClient

client = MetadataClient(
    "Host=localhost;Port=5433;Database=vcbncvbn;Username=vbncvbn;Password=bvncvbn;"
)

# Информация о конфигурации
print(f"Конфигурация: {client.config_name}")
print(f"Синоним: {client.config_alias}")
print(f"Версия платформы: {client.platform_version}")

# Список типов объектов
types = client.list_types()
print(types)  # ['Справочники', 'Документы', ...]

# Список объектов конкретного типа
objects = client.list_objects("Справочники")
for obj in objects:
    print(f"  {obj['name']} → таблица {obj['table']}")
    for prop in obj['properties']:
        print(f"    {prop['name']}")
        for col in prop.get('columns', []):
            print(f"      {col['name']}: {col['type']}")
```

### Структура объекта метаданных

```
MetadataClient
└── list_objects(type_name) → list[dict]
    ├── 'name': str           # Полное имя (например, "Справочник.Контрагенты")
    ├── 'short_name': str     # Короткое имя (например, "Контрагенты")
    ├── 'table': str          # Имя таблицы в БД (например, "_Reference53")
    ├── 'properties': list    # Список реквизитов
    │   ├── 'name': str       # Человеческое имя (например, "Наименование")
    │   └── 'columns': list   # Колонки в БД
    │       ├── 'name': str   # Имя колонки (например, "_Description")
    │       └── 'type': str   # Тип колонки (например, "string(150)")
    └── 'children': list      # Табличные части
        ├── 'name': str       # Имя табличной части
        ├── 'table': str      # Имя таблицы в БД
        └── 'properties': list
```

---

## Слой данных (pydajet_metadata)

### Query Builder

Построитель запросов с человеческими названиями колонок.

```python
from pydajet_metadata import Query

# Получение Query через Repository
query = repo.query("Справочники", "ирАлгоритмы")

# Все записи
rows = query.all()
for row in rows:
    print(f"{row['Наименование']}: {row['ТекстАлгоритма'][:50]}...")

# Первая запись
first = query.first()
print(first['Наименование'])

# Количество записей
count = query.count()
print(f"Всего: {count}")

# Фильтрация
filtered = query.where(query.Наименование == 'telegram').all()
```

### Операции записи

```python
# Добавление
new_id = query.Добавить({
    'Наименование': 'Новый алгоритм',
    'ТекстАлгоритма': 'Сообщить("Привет");',
    'ДатаИзменения': datetime.now(),
})
print(f"Создана запись: {new_id}")

# Изменение
updated = query.Изменить(new_id, {
    'Наименование': 'Обновлённый алгоритм',
})
print(f"Обновлено: {updated}")

# Удаление
deleted = query.Удалить(new_id)
print(f"Удалено: {deleted}")
```

### Работа с табличными частями

```python
# Просмотр табличных частей
print(query.ТабличныеЧасти)
# ['Получатели']

# Доступ к табличной части
child_query = query.Часть('Получатели')

# Добавление с табличной частью
new_doc_id = query.ДобавитьСЧастями(
    data={
        'Дата': datetime.now(),
        'Номер': '0000001',
        'Проведен': True,
        'Сообщение': 'Тестовое уведомление',
    },
    части={
        'Получатели': [
            {'Сотрудник': 'Иванов', 'Статус': 'Новый'},
            {'Сотрудник': 'Петров', 'Статус': 'Прочитано'},
        ]
    }
)
```

### Таблица методов Query

| Метод | Описание | Возвращает |
|-------|----------|------------|
| `all()` | Все записи | `list[dict]` |
| `first()` | Первая запись | `dict` или `None` |
| `count()` | Количество записей | `int` |
| `where(*conditions)` | Условие фильтрации | `self` |
| `Добавить(data)` | Добавить запись | `str` (UUID) |
| `Изменить(id, data)` | Изменить запись | `bool` |
| `Удалить(id)` | Удалить запись | `bool` |
| `ДобавитьСЧастями(data, части)` | Добавить с ТЧ | `str` (UUID) |
| `lock(mode, row_id, nowait)` | Блокировка | `None` |

---

## Генератор API (FastAPI)

Автоматически создаёт REST API для всех объектов 1С с OpenAPI-документацией.

### Генерация и запуск

```python
from pydajet_metadata import Repository, APIGenerator

repo = Repository("Host=localhost;Port=5433;Database=vbncvbncvnb;Username=vcbncvbncvnb;Password=vcbncvbncv;")

# Генерируем API
api = APIGenerator(repo, title="MessageCenter API")
app = api.generate()

# Запускаем сервер
api.run(host="0.0.0.0", port=8000)
```

### Сгенерированные endpoints

| Метод | URL | Описание |
|-------|-----|----------|
| `GET` | `/{тип}/{объект}` | Все записи |
| `GET` | `/{тип}/{объект}/{id}` | Запись по ID |
| `POST` | `/{тип}/{объект}` | Создать запись |
| `PUT` | `/{тип}/{объект}/{id}` | Обновить запись |
| `DELETE` | `/{тип}/{объект}/{id}` | Удалить запись |
| `GET` | `/{тип}/{объект}/count` | Количество записей |
| `GET` | `/types` | Список типов объектов |
| `GET` | `/types/{тип}/objects` | Список объектов типа |

### Документация API

- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`
- **OpenAPI JSON:** `http://localhost:8000/openapi.json`

---

## Polars-интеграция

Высокопроизводительная работа с данными через Polars DataFrame.

### Чтение и запись

```python
from pydajet_metadata import PolarsBridge

bridge = PolarsBridge(repo)

# Чтение всей таблицы
df = bridge.read("Справочники", "ирАлгоритмы")
print(f"Загружено {df.height} записей")

# Массовая вставка
new_data = pl.DataFrame([
    {"Наименование": "Алгоритм 1", "ТекстАлгоритма": '...'},
    {"Наименование": "Алгоритм 2", "ТекстАлгоритма": '...'},
])
count = bridge.write(new_data, "Справочники", "ирАлгоритмы", mode="append")
print(f"Вставлено {count} записей")

# Массовое обновление (замена всех записей)
df = bridge.read("Справочники", "ирАлгоритмы")
df = df.with_columns(
    pl.when(pl.col("Наименование").str.contains("telegram"))
    .then(pl.lit("Обновлённый"))
    .otherwise(pl.col("Наименование"))
    .alias("Наименование")
)
bridge.write(df, "Справочники", "ирАлгоритмы", mode="replace")
```

### Аналитика

```python
analytics = bridge.analytics("Справочники", "ирАлгоритмы")

# Цепочка операций
result = (
    analytics
    .filter(pl.col("Наименование").str.contains("telegram"))
    .select("Наименование", "ДатаИзменения")
    .sort("ДатаИзменения", descending=True)
    .collect()
)

# Группировка
grouped = analytics.group_by("ДатаИзменения").sort("len", descending=True)
print(grouped.collect())
```

---

## Динамические Pydantic-модели

Генератор моделей из метаданных 1С для валидации и сериализации.

### Генерация моделей

```python
from pydajet_metadata import SchemaGenerator

gen = SchemaGenerator(repo)

# Получить модель
Алгоритм = gen.get("Справочники.ирАлгоритмы")
```

### Работа с моделями

```python
# Создание
alg = Алгоритм(
    Наименование="Тестовый",
    ТекстАлгоритма='Сообщить("Привет");',
    ДатаИзменения=datetime.now(),
)
alg.save()
print(f"ID: {alg.Ссылка}")

# Загрузка из БД
alg2 = Алгоритм.from_db(alg.Ссылка)
print(f"Наименование: {alg2.Наименование}")

# Изменение
alg2.Наименование = "Обновлённый"
alg2.save()

# Удаление
alg2.delete()

# Все записи
for a in Алгоритм.all():
    print(a.Наименование)

# Сериализация в JSON
json_str = alg.model_dump_json()
```

---

## Транзакции и блокировки

### Транзакции

```python
# Простая транзакция
with repo.session.transaction():
    repo.Справочники['ирАлгоритмы'].Добавить({...})
    repo.Документы['Уведомления'].Добавить({...})
# Автоматический commit при выходе без ошибок
# Автоматический rollback при исключении

# Вложенная транзакция (savepoint)
with repo.session.transaction():
    repo.Справочники['ирАлгоритмы'].Добавить({...})
    
    try:
        with repo.session.savepoint():
            repo.Документы['Уведомления'].Добавить({...})
            raise Exception("Ошибка")
    except Exception:
        pass  # Документ откатится, справочник сохранится
```

### Блокировки

```python
query = repo.query("Справочники", "ирАлгоритмы")

# Блокировка всей таблицы (эксклюзивная)
with repo.session.transaction():
    query.lock(mode="exclusive")
    # Массовое обновление

# Блокировка строки (разделяемая)
with repo.session.transaction():
    query.lock(mode="shared", row_id="...")
    # Чтение с гарантией, что запись не изменится

# Блокировка без ожидания
try:
    query.lock(mode="exclusive", nowait=True)
except OperationalError:
    print("Таблица занята")
```

### Типы блокировок

| Режим | SQL | Описание |
|-------|-----|----------|
| `shared` | `FOR SHARE` / `LOCK TABLE ... IN SHARE MODE` | Другие читают, но не пишут |
| `exclusive` | `FOR UPDATE` / `LOCK TABLE ... IN EXCLUSIVE MODE` | Никто не читает и не пишет |
| `nowait` | `NOWAIT` | Ошибка, если блокировка занята |

---

## UUID-конвертация

1С хранит UUID в особом формате — первые 8 байт переставлены местами. Модуль `_uuid.py` обеспечивает прозрачную конвертацию.

### Функции конвертации

```python
from pydajet_metadata._uuid import from_1c, to_1c, generate, format_uuid

# 1С-байты → стандартный UUID
std_uuid = from_1c(b'\x9c\x28\x00\x50\xb6\x66\xdf\xfa\x11\xf1\x4e\x88\x0e\x76\x1a\xbe')
print(std_uuid)  # UUID('5000289c-66b6-fadf-11f1-4e880e761abe')

# Стандартный UUID → 1С-байты
c1_bytes = to_1c(std_uuid)

# Генерация нового UUID
new_uuid = generate()

# Форматирование с дефисами
formatted = format_uuid(std_uuid)
print(formatted)  # '5000289c-66b6-fadf-11f1-4e880e761abe'
```

### Где применяется

| Операция | Конвертация |
|----------|-------------|
| Чтение из БД | 1С-байты → UUID с дефисами |
| Запись в БД | UUID с дефисами → 1С-байты |
| Отображение | Всегда UUID с дефисами |

---

## Тестирование

### Запуск тестов

```bash
# Все тесты
pytest

# Конкретный файл
pytest tests/test_uuid.py -v

# С покрытием
pytest --cov=src/pydajet --cov=src/pydajet_metadata --cov-report=html
```

### Структура тестов

| Файл | Что тестирует | Кол-во тестов |
|------|--------------|---------------|
| `test_uuid.py` | UUID-конвертация | 12 |
| `test_types.py` | Маппинг типов | 20 |
| `test_session.py` | Подключение и транзакции | 6 |
| `test_query.py` | Query builder + блокировки | 12 |
| `test_repository.py` | Repository | 5 |
| `test_api.py` | FastAPI-эндпоинты | 10 |
| `test_schema.py` | Pydantic-модели | 1 |
| `test_polars_bridge.py` | Polars-интеграция | 2 |
| **Всего** | | **68** |

### Покрытие кода

| Модуль | Покрытие |
|--------|----------|
| `_uuid.py` | 95% |
| `_types.py` | 100% |
| `api.py` | 93% |
| `query.py` | 66% |
| `repository.py` | 68% |
| `session.py` | 42% |
| `bridge.py` | 51% |
| `schema.py` | 54% |
| **Общее** | **59%** |
