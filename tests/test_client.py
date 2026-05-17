"""Тесты MetadataClient."""
import pytest
from unittest.mock import MagicMock , patch , PropertyMock
from pydajet.client import MetadataClient


class TestMetadataClient :
	"""Тесты клиента метаданных."""

	def test_type_by_prefix ( self ) :
		assert MetadataClient._type_by_prefix ( "Справочник.ирАлгоритмы" ) == "Справочники"
		assert MetadataClient._type_by_prefix ( "Документ.Уведомления" ) == "Документы"
		assert MetadataClient._type_by_prefix ( "Константа.КлючШифрования" ) == "Константы"
		assert MetadataClient._type_by_prefix ( "РегистрСведений.Значения" ) == "РегистрыСведений"
		assert MetadataClient._type_by_prefix ( "ПланВидовХарактеристик.Параметры" ) == "ПланыВидовХарактеристик"
		assert MetadataClient._type_by_prefix ( "Неизвестный.Объект" ) == "Неизвестный"

	@patch ( 'dajet.client.MetadataProvider' )
	def test_init ( self , mock_provider ) :
		mock_result = MagicMock ( )
		mock_config = MagicMock ( )
		mock_config.Name = "ТестоваяКонфигурация"
		mock_config.Alias = "Тест"
		mock_config.Metadata.Keys = [ ]
		mock_result.GetConfigurations.return_value = [ mock_config ]
		mock_provider.Create.return_value = (mock_result , True)

		client = MetadataClient ( "Host=localhost;Database=TestDB;Username=test;Password=test;" )

		assert client.config_name == "ТестоваяКонфигурация"
		assert client.config_alias == "Тест"
		assert client.list_types ( ) == [ ]
