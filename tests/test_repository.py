"""Тесты Repository."""
import sys
import pytest
from unittest.mock import MagicMock, patch
from pydajet_metadata.exceptions import MetadataOutdatedError
from pydajet_metadata.repository import Repository, TypeAccessor


@pytest.fixture(autouse=True, scope='module')
def mock_pydajet():
    """Подменяет pydajet на моки, чтобы избежать импорта .NET."""
    # Если pydajet ещё не загружен (тесты без .NET), подменяем
    if 'pydajet' not in sys.modules:
        mock = MagicMock()
        mock.MetadataClient = MagicMock()
        sys.modules['pydajet'] = mock
        sys.modules['pydajet.client'] = mock
        sys.modules['pydajet._uuid'] = MagicMock()
        sys.modules['pydajet._platform'] = MagicMock()
    yield


class TestRepository:
    """Тесты репозитория."""

    @pytest.fixture
    def mock_client(self):
        client = MagicMock()
        client.list_types.return_value = ['Справочники', 'Документы']
        client.list_objects.return_value = [
            {
                'name': 'Справочник.ирАлгоритмы',
                'short_name': 'ирАлгоритмы',
                'table': '_Reference53',
                'properties': [
                    {'name': 'Ссылка', 'columns': [{'name': '_IDRRef', 'type': 'binary(16,fixed)'}]},
                    {'name': 'Наименование', 'columns': [{'name': '_Description', 'type': 'string(150)'}]},
                ],
                'children': [],
            },
        ]
        return client

    @pytest.fixture
    def mock_session(self):
        session = MagicMock()
        session.reflect_table = MagicMock()
        session.get_pk = MagicMock(return_value='_idrref')
        return session

    def test_types(self, mock_client, mock_session):
        with patch('pydajet_metadata.repository.Session', return_value=mock_session):
            with patch('pydajet.client.MetadataClient', return_value=mock_client):
                repo = Repository("Host=localhost;Database=TestDB;Username=test;Password=test;")
                assert repo.types() == ['Документы', 'Справочники']

    def test_objects(self, mock_client, mock_session):
        with patch('pydajet_metadata.repository.Session', return_value=mock_session):
            with patch('pydajet.client.MetadataClient', return_value=mock_client):
                repo = Repository("Host=localhost;Database=TestDB;Username=test;Password=test;")
                objects = repo.objects('Справочники')
                assert 'ирАлгоритмы' in objects

    def test_query(self, mock_client, mock_session):
        with patch('pydajet_metadata.repository.Session', return_value=mock_session):
            with patch('pydajet.client.MetadataClient', return_value=mock_client):
                repo = Repository("Host=localhost;Database=TestDB;Username=test;Password=test;")
                q = repo.query('Справочники', 'ирАлгоритмы')
                assert q is not None

    def test_query_invalid_type(self, mock_client, mock_session):
        with patch('pydajet_metadata.repository.Session', return_value=mock_session):
            with patch('pydajet.client.MetadataClient', return_value=mock_client):
                repo = Repository("Host=localhost;Database=TestDB;Username=test;Password=test;")
                with pytest.raises(KeyError):
                    repo.query('НесуществующийТип', 'Объект')

    def test_repository_accepts_protocol_client_without_pydajet(
        self, mock_client, mock_session, monkeypatch
    ):
        monkeypatch.setitem(sys.modules, 'pydajet', None)
        monkeypatch.setitem(sys.modules, 'pydajet.client', None)

        with patch('pydajet_metadata.repository.Session', return_value=mock_session):
            repo = Repository(client=mock_client, session=mock_session)
            assert repo._client is mock_client
            assert repo.types() == ['Документы', 'Справочники']

    def test_client_factory_requires_connection_string(self, mock_client, mock_session):
        with pytest.raises(ValueError):
            Repository(client_factory=lambda cs, ds: mock_client, session=mock_session)

    def test_connection_string_required_without_client_or_session(self, mock_session):
        with pytest.raises(ValueError):
            Repository(session=mock_session)

    def test_repository_client_factory(self, mock_client, mock_session):
        with patch('pydajet_metadata.repository.Session', return_value=mock_session):
            repo = Repository(
                connection_string="Host=localhost;Database=TestDB;Username=test;Password=test;",
                client_factory=lambda cs, ds: mock_client,
                session=mock_session,
            )
            assert repo._client is mock_client

    def test_check_metadata_actual_raises_when_root_guid_changes(self, mock_client, mock_session):
        mock_client.list_types.return_value = []
        mock_client.list_objects.return_value = []
        mock_session.reflect_table.return_value = MagicMock()
        with patch('pydajet_metadata.repository.Session', return_value=mock_session):
            repo = Repository(client=mock_client, session=mock_session)
            repo._root_guid = 'old'
            repo._get_root_guid = MagicMock(return_value='new')
            with pytest.raises(MetadataOutdatedError):
                repo.check_metadata_actual()

    def test_refresh_metadata_rebuilds_queries(self, mock_client, mock_session):
        mock_client.list_types.return_value = []
        mock_client.list_objects.return_value = []
        mock_session.reflect_table.return_value = MagicMock()
        with patch('pydajet_metadata.repository.Session', return_value=mock_session):
            repo = Repository(client=mock_client, session=mock_session)
            repo._root_guid = 'old'
            repo._get_root_guid = MagicMock(return_value='new')
            repo._build = MagicMock()
            repo.refresh_metadata()
            repo._build.assert_called_once()
            assert repo.root_guid == 'new'

    def test_objects_unknown_type_returns_empty_list(self, mock_client, mock_session):
        with patch('pydajet_metadata.repository.Session', return_value=mock_session):
            with patch('pydajet.client.MetadataClient', return_value=mock_client):
                repo = Repository("Host=localhost;Database=TestDB;Username=test;Password=test;")
                assert repo.objects('Неизвестный') == []

    def test_query_invalid_object_raises(self, mock_client, mock_session):
        with patch('pydajet_metadata.repository.Session', return_value=mock_session):
            with patch('pydajet.client.MetadataClient', return_value=mock_client):
                repo = Repository("Host=localhost;Database=TestDB;Username=test;Password=test;")
                with pytest.raises(KeyError):
                    repo.query('Справочники', 'НеизвестныйОбъект')

    def test_attr_access(self, mock_client, mock_session):
        with patch('pydajet_metadata.repository.Session', return_value=mock_session):
            with patch('pydajet.client.MetadataClient', return_value=mock_client):
                repo = Repository("Host=localhost;Database=TestDB;Username=test;Password=test;")
                accessor = repo.Справочники
                assert isinstance(accessor, TypeAccessor)
                assert accessor.list() == ['ирАлгоритмы']
