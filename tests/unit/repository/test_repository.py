"""Unit tests for Repository - изолированные тесты без подключения к БД."""
from unittest.mock import MagicMock, Mock, patch, call

import pytest

from pydajet_metadata.exceptions import MetadataOutdatedError
from pydajet_metadata.repository import Repository, TypeAccessor


@pytest.fixture
def mock_metadata_client():
    """Фикстура с замоканым MetadataClient."""
    client = Mock()
    client.platform_version = 123
    client.list_types.return_value = ["Catalog", "Document"]
    client.list_objects.side_effect = lambda t: [
        {
            "short_name": "Products",
            "table": "_Reference123",
            "properties": [
                {"name": "id", "columns": [{"name": "_idrref"}]},
                {"name": "name", "columns": [{"name": "name"}]}
            ],
            "children": [
                {
                    "name": "tabular_part",
                    "table": "_AccRg123",
                    "properties": [
                        {"name": "id", "columns": [{"name": "_idrref"}]},
                        {"name": "owner", "columns": [{"name": "_idrref_owner"}]},
                        {"name": "value", "columns": [{"name": "value"}]}
                    ]
                }
            ]
        }
    ] if t == "Catalog" else []
    return client


@pytest.fixture
def mock_session():
    """Фикстура с замоканым Session."""
    session = Mock()
    session.get_pk.return_value = "_idrref"
    session.reflect_table = Mock(return_value=Mock(c={"_FileName": Mock()}))
    session.engine = MagicMock()
    session.engine.connect.return_value.__enter__.return_value.execute.return_value.scalar.return_value = b"0123456789abcdef"
    session.close = Mock()
    return session


@pytest.fixture
def repository(mock_metadata_client, mock_session):
    """Фикстура с экземпляром Repository."""
    with patch("pydajet_metadata.repository.MetadataClient", return_value=mock_metadata_client):
        with patch("pydajet_metadata.repository.Session", return_value=mock_session):
            repo = Repository(connection_string="test://db", data_source="postgresql")
            return repo


class TestRepositoryInit:
    """Тесты инициализации Repository."""

    def test_init_creates_client_and_session(self, mock_metadata_client, mock_session):
        """Проверка создания клиента и сессии."""
        with patch("pydajet_metadata.repository.MetadataClient", return_value=mock_metadata_client) as mock_client_cls:
            with patch("pydajet_metadata.repository.Session", return_value=mock_session) as mock_session_cls:
                repo = Repository(connection_string="test://db", data_source="postgresql")
                
                mock_client_cls.assert_called_once_with("test://db", "postgresql")
                mock_session_cls.assert_called_once_with("test://db", "postgresql")

    def test_init_stores_platform_version(self, mock_metadata_client, mock_session):
        """Проверка сохранения версии платформы."""
        with patch("pydajet_metadata.repository.MetadataClient", return_value=mock_metadata_client):
            with patch("pydajet_metadata.repository.Session", return_value=mock_session):
                repo = Repository("test://db")
                assert repo.metadata_version == 123

    def test_init_builds_queries(self, mock_metadata_client, mock_session):
        """Проверка построения кэша запросов."""
        with patch("pydajet_metadata.repository.MetadataClient", return_value=mock_metadata_client):
            with patch("pydajet_metadata.repository.Session", return_value=mock_session):
                repo = Repository("test://db")
                
                assert "Catalog" in repo._queries
                assert "Products" in repo._queries["Catalog"]


class TestRepositoryTypesAndObjects:
    """Тесты методов types() и objects()."""

    def test_types_returns_sorted_list(self, repository):
        """Метод types возвращает отсортированный список типов."""
        types = repository.types()
        assert types == sorted(["Catalog", "Document"])

    def test_objects_returns_sorted_list(self, repository):
        """Метод objects возвращает отсортированный список объектов."""
        objects = repository.objects("Catalog")
        assert objects == ["Products"]

    def test_objects_unknown_type_returns_empty(self, repository):
        """Запрос объектов неизвестного типа возвращает пустой список."""
        objects = repository.objects("UnknownType")
        assert objects == []


class TestRepositoryQuery:
    """Тесты метода query()."""

    def test_query_returns_query_object(self, repository):
        """Метод query возвращает Query объект."""
        from pydajet_metadata.query import Query
        
        query = repository.query("Catalog", "Products")
        assert isinstance(query, Query)

    def test_query_unknown_type_raises_keyerror(self, repository):
        """Запрос неизвестного типа вызывает KeyError."""
        with pytest.raises(KeyError, match="Type 'Unknown' not found"):
            repository.query("Unknown", "Products")

    def test_query_unknown_object_raises_keyerror(self, repository):
        """Запрос неизвестного объекта вызывает KeyError."""
        with pytest.raises(KeyError, match="Object 'Unknown' not found in 'Catalog'"):
            repository.query("Catalog", "Unknown")


class TestRepositoryAttributeAccess:
    """Тесты доступа через __getattr__."""

    def test_getattr_known_type_returns_accessor(self, repository):
        """Доступ к известному типу возвращает TypeAccessor."""
        accessor = repository.Catalog
        assert isinstance(accessor, TypeAccessor)
        assert accessor._type == "Catalog"

    def test_getattr_unknown_type_raises_attributeerror(self, repository):
        """Доступ к неизвестному типу вызывает AttributeError."""
        with pytest.raises(AttributeError, match="Type 'Unknown' not found"):
            _ = repository.Unknown

    def test_type_accessor_getitem_returns_query(self, repository):
        """TypeAccessor.__getitem__ возвращает Query."""
        from pydajet_metadata.query import Query
        
        accessor = repository.Catalog
        query = accessor["Products"]
        assert isinstance(query, Query)

    def test_type_accessor_getattr_returns_query(self, repository):
        """TypeAccessor.__getattr__ возвращает Query."""
        from pydajet_metadata.query import Query
        
        accessor = repository.Catalog
        query = accessor.Products
        assert isinstance(query, Query)

    def test_type_accessor_list_returns_objects(self, repository):
        """TypeAccessor.list возвращает список объектов."""
        accessor = repository.Catalog
        objects = accessor.list()
        assert objects == ["Products"]


class TestRepositoryMetadataManagement:
    """Тесты управления метаданными."""

    def test_root_guid_property(self, repository):
        """Свойство root_guid возвращает GUID."""
        assert isinstance(repository.root_guid, str)

    def test_check_metadata_actual_no_change(self, repository, mock_session):
        """Проверка актуальности при отсутствии изменений не вызывает ошибку."""
        # GUID не изменился
        repository.check_metadata_actual()  # Не должно вызывать исключений

    def test_check_metadata_actual_changed_raises(self, repository, mock_session):
        """Проверка актуальности при изменении GUID вызывает MetadataOutdatedError."""
        # Меняем возвращаемый GUID
        mock_session.engine.connect.return_value.__enter__.return_value.execute.return_value.scalar.return_value = b"fedcba9876543210"
        
        with pytest.raises(MetadataOutdatedError) as exc_info:
            repository.check_metadata_actual()
        
        assert "Metadata configuration has changed" in str(exc_info.value)
        assert "Old root GUID" in str(exc_info.value)
        assert "New root GUID" in str(exc_info.value)

    def test_check_metadata_actual_empty_guid_no_error(self, repository, mock_session):
        """Пустой GUID не вызывает ошибку."""
        mock_session.engine.connect.return_value.__enter__.return_value.execute.return_value.scalar.return_value = None
        
        repository.check_metadata_actual()  # Не должно вызывать исключений

    def test_refresh_metadata_clears_and_rebuilds(self, repository, mock_metadata_client):
        """refresh_metadata очищает кэш и перестраивает запросы."""
        # Сохраняем старое состояние
        old_queries = repository._queries.copy()
        
        # Меняем моки для имитации изменений
        mock_metadata_client.list_objects.return_value = []
        
        repository.refresh_metadata()
        
        # Проверяем, что кэш перестроен
        assert repository._queries is not old_queries
        # Объекты должны быть пустыми после перестройки с пустыми данными
        assert repository.objects("Catalog") == []

    def test_close_closes_session(self, repository, mock_session):
        """Метод close закрывает сессии."""
        repository.close()
        mock_session.close.assert_called_once()


class TestRepositoryBuildLogic:
    """Тесты логики метода _build()."""

    def test_build_maps_columns(self, mock_metadata_client, mock_session):
        """_build правильно маппит колонки."""
        with patch("pydajet_metadata.repository.MetadataClient", return_value=mock_metadata_client):
            with patch("pydajet_metadata.repository.Session", return_value=mock_session):
                repo = Repository("test://db")
                query = repo.query("Catalog", "Products")
                
                # Проверяем, что маппинг создан
                assert "id" in query._column_map
                assert "name" in query._column_map
                assert query._column_map["id"] == "_idrref"

    def test_build_detects_primary_key(self, mock_metadata_client, mock_session):
        """_build определяет первичный ключ."""
        with patch("pydajet_metadata.repository.MetadataClient", return_value=mock_metadata_client):
            with patch("pydajet_metadata.repository.Session", return_value=mock_session):
                repo = Repository("test://db")
                query = repo.query("Catalog", "Products")
                
                assert query._pk == "_idrref"

    def test_build_nests_children(self, mock_metadata_client, mock_session):
        """_build вкладывает дочерние запросы."""
        with patch("pydajet_metadata.repository.MetadataClient", return_value=mock_metadata_client):
            with patch("pydajet_metadata.repository.Session", return_value=mock_session):
                repo = Repository("test://db")
                query = repo.query("Catalog", "Products")
                
                assert "tabular_part" in query._children
                # Проверяем доступ через атрибут
                assert hasattr(query, "tabular_part")

    def test_build_child_owner_key_detection(self, mock_metadata_client, mock_session):
        """_build определяет ключ владельца для дочерних таблиц."""
        with patch("pydajet_metadata.repository.MetadataClient", return_value=mock_metadata_client):
            with patch("pydajet_metadata.repository.Session", return_value=mock_session):
                repo = Repository("test://db")
                query = repo.query("Catalog", "Products")
                
                child_query = query._children["tabular_part"]
                assert child_query._owner_key == "_idrref_owner"


class TestRepositoryEdgeCases:
    """Тесты граничных случаев."""

    def test_build_with_empty_properties(self, mock_metadata_client, mock_session):
        """_build обрабатывает объекты без свойств."""
        mock_metadata_client.list_objects.return_value = [
            {
                "short_name": "Empty",
                "table": "_Empty",
                "properties": [],
                "children": []
            }
        ]
        
        with patch("pydajet_metadata.repository.MetadataClient", return_value=mock_metadata_client):
            with patch("pydajet_metadata.repository.Session", return_value=mock_session):
                repo = Repository("test://db")
                query = repo.query("Catalog", "Empty")
                
                # Проверяем, что запрос создан с пустым маппингом
                assert query._column_map == {}

    def test_get_root_guid_exception_returns_empty(self, mock_session):
        """_get_root_guid при ошибке возвращает пустую строку."""
        mock_session.reflect_table.side_effect = Exception("DB error")
        
        with patch("pydajet_metadata.repository.Session", return_value=mock_session):
            with patch("pydajet_metadata.repository.MetadataClient"):
                repo = Repository("test://db")
                assert repo.root_guid == ""

    def test_session_property(self, repository, mock_session):
        """Свойство session возвращает сессию."""
        assert repository.session is mock_session
