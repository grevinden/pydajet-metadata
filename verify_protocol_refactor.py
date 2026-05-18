"""Быстрая проверка импортов после рефакторинга на Protocol."""
import sys
sys.path.insert(0, r"C:\Users\rasty\Projects\pydajet-metadata-qwen\src")

print("🔍 Проверка импортов...")

try:
    # 1. Проверяем что протоколы импортируются
    from pydajet_metadata.protocols import (
        ISession, IQuery, IColumnMapper, IMetadataClient, IRepository
    )
    print("✅ Протоколы импортированы успешно")

    # 2. Проверяем что основные классы импортируются
    from pydajet_metadata import (
        Repository, Query, Session, SchemaGenerator, PolarsBridge, APIGenerator,
        ISession, IQuery, IColumnMapper, IMetadataClient, IRepository
    )
    print("✅ Основные классы и протоколы экспортируются из __init__")

    # 3. Проверяем что Query имеет _column_map property
    assert hasattr(Query, '_column_map'), "Query missing _column_map property"
    print("✅ Query._column_map property существует")

    # 4. Проверяем сигнатуры
    import inspect
    repo_sig = inspect.signature(Repository.__init__)
    assert 'client' in repo_sig.parameters, "Repository missing client param"
    assert 'session' in repo_sig.parameters, "Repository missing session param"
    print("✅ Repository поддерживает DI через client/session")

    bridge_sig = inspect.signature(PolarsBridge.__init__)
    # Аннотация может быть строковой, проверяем наличие параметра
    assert 'repo' in bridge_sig.parameters, "PolarsBridge missing repo param"
    print("✅ PolarsBridge принимает repo параметр")

    schema_sig = inspect.signature(SchemaGenerator.__init__)
    assert 'repo' in schema_sig.parameters, "SchemaGenerator missing repo param"
    print("✅ SchemaGenerator принимает repo параметр")

    print("\n🎉 Все проверки пройдены! Архитектура на Protocol внедрена успешно.")

except Exception as e:
    print(f"❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
