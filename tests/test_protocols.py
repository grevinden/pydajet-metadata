"""Тесты протоколов pydajet_metadata."""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch
from sqlalchemy import Column, LargeBinary, MetaData, Table

from pydajet_metadata.mapper import ColumnMapper
from pydajet_metadata.protocols import (
    IColumnMapper,
    IMetadataClient,
    IQuery,
    IRepository,
    ISession,
)
from pydajet_metadata.query import Query
from pydajet_metadata.repository import Repository
from pydajet_metadata.session import Session


class DummyMetadataClient:
    platform_version = 123

    def list_types(self) -> list[str]:
        return []

    def list_objects(self, type_name: str) -> list[dict[str, Any]]:
        return []


class TestProtocols:
    def test_session_implements_isession(self, sample_connection_string):
        with patch('pydajet_metadata.session.create_engine') as mock_engine:
            with patch('pydajet_metadata.session.inspect') as mock_inspect:
                session = Session(sample_connection_string)
                assert isinstance(session, ISession)

    def test_column_mapper_implements_icolumnmapper(self, mapper_sample_table, mapper_sample_column_map):
        mapper = ColumnMapper(mapper_sample_table, mapper_sample_column_map)
        assert isinstance(mapper, IColumnMapper)

    def test_query_implements_iquery(self, mock_session, mapper_sample_column_map):
        table = Table(
            '_reference53',
            MetaData(),
            Column('_idrref', LargeBinary),
        )
        mock_session.reflect_table.return_value = table
        query = Query(mock_session, '_reference53', mapper_sample_column_map)
        assert isinstance(query, IQuery)
        assert query._pk == '_idrref'

    def test_repository_implements_irepository(self, mock_repo_session):
        client = MagicMock()
        client.platform_version = 1
        client.list_types.return_value = ['Catalog']
        client.list_objects.return_value = [
            {
                'name': 'Справочник.Тест',
                'short_name': 'Тест',
                'table': '_Reference53',
                'properties': [{'name': 'Ссылка', 'columns': [{'name': '_IDRRef'}]}],
                'children': [],
            }
        ]
        repo = Repository(client=client, session=mock_repo_session)
        assert isinstance(repo, IRepository)

    def test_metadata_client_protocol_runtime_check(self):
        client = DummyMetadataClient()
        assert isinstance(client, IMetadataClient)
        assert client.list_types() == []
