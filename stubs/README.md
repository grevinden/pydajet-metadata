# Локальные stubs (pydajet-metadata)

Частичные type stubs для **pythonnet / DaJet**, которые реально использует пакет `pydajet`.
Это **не** официальные stubs pythonnet; их поддерживает этот репозиторий.

Покрыто:

- `clr.AddReference`
- `DaJet.Metadata.MetadataProvider` (Create, GetConfigurations, ResolveReferences, GetMetadataObject, PlatformVersion)
- `DaJet.Data.DataSourceType` (PostgreSql, SqlServer)
- `System.Guid`
- `System.Collections.Generic.List` (конструктор, Add, Count, индексация)

Mypy подхватывает каталог через `mypy_path` в `pyproject.toml`.

При добавлении новых вызовов в .NET — расширяйте соответствующий `.pyi` здесь.
