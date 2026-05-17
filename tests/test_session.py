"""Тесты Session."""
import pytest
from unittest.mock import MagicMock, patch
from pydajet_metadata.session import Session

pytest.importorskip("pydajet_metadata.session", reason="Требуется .NET Runtime")


class TestSession:
    """Тесты сессии подключения к БД."""

    def test_parse_connection_string(self, sample_connection_string):
        session = Session.__new__(Session)
        params = session._parse_cs(sample_connection_string)
        assert params == {
            'host': 'localhost',
            'port': '5433',
            'database': 'TestDB',
            'username': 'test',
            'password': 'test',
        }

    def test_parse_cs_case_insensitive(self):
        cs = "HOST=Server;PORT=5432;DATABASE=DB;USERNAME=U;PASSWORD=P"
        session = Session.__new__(Session)
        result = session._parse_cs(cs)
        assert result == {
            'host': 'Server',
            'port': '5432',
            'database': 'DB',
            'username': 'U',
            'password': 'P',
        }

    def test_parse_cs_empty(self):
        session = Session.__new__(Session)
        assert session._parse_cs("") == {}

    def test_parse_cs_extra_semicolons(self):
        cs = "Host=localhost;;Port=5432;"
        session = Session.__new__(Session)
        result = session._parse_cs(cs)
        assert result == {'host': 'localhost', 'port': '5432'}

    @patch('pydajet_metadata.session.inspect')
    @patch('pydajet_metadata.session.create_engine')
    def test_init_creates_engine(self, mock_engine, mock_inspect, sample_connection_string):
        session = Session(sample_connection_string)
        mock_engine.assert_called_once()
        assert session._engine is not None

    @patch('pydajet_metadata.session.inspect')
    @patch('pydajet_metadata.session.create_engine')
    def test_close_disposes_engine(self, mock_engine, mock_inspect, sample_connection_string):
        session = Session(sample_connection_string)
        session._engine.dispose = MagicMock()
        session.close()
        session._engine.dispose.assert_called_once()
