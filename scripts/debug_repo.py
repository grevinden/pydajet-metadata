from unittest.mock import Mock, MagicMock, patch
from pydajet_metadata.repository import Repository

mock_metadata_client = Mock()
mock_metadata_client.platform_version = 123
mock_metadata_client.list_types.return_value = ['Catalog']
mock_metadata_client.list_objects.return_value = [
    {
        'short_name': 'Products',
        'table': '_Reference123',
        'properties': [{'name': 'id', 'columns': [{'name': '_idrref'}]}],
        'children': [],
    }
]

mock_session = Mock()
mock_session.get_pk.return_value = '_idrref'
mock_session.reflect_table = Mock(return_value=Mock(c={'_FileName': Mock()}))
mock_session.engine = MagicMock()
mock_session.engine.connect.return_value.__enter__.return_value.execute.return_value.scalar.return_value = b'0123456789abcdef'

with patch('pydajet_metadata.repository.MetadataClient', return_value=mock_metadata_client):
    with patch('pydajet_metadata.repository.Session', return_value=mock_session):
        repo = Repository(connection_string='test://db', data_source='postgresql')
        print('initial root_guid:', repo.root_guid)
        mock_session.engine.connect.return_value.__enter__.return_value.execute.return_value.scalar.return_value = b'fedcba9876543210'
        try:
            repo.check_metadata_actual()
            print('check_metadata_actual: did not raise')
        except Exception as e:
            print('raised:', type(e), e)
