"""Тесты UUID-конвертации."""
import pytest
from uuid import UUID
from hypothesis import given, strategies as st

# Импортируем напрямую, минуя pydajet/__init__.py (который тянет .NET)
from pydajet._uuid import from_1c, to_1c, generate, format_uuid


class TestUUIDConversion:
	"""Конвертация 1С ↔ стандартный UUID."""

	def test_from_1c_to_standard ( self , sample_uuid_bytes , sample_uuid ) :
		result = from_1c ( sample_uuid_bytes )
		assert result == sample_uuid
		assert isinstance ( result , UUID )

	def test_to_1c_from_uuid ( self , sample_uuid , sample_uuid_bytes ) :
		result = to_1c ( sample_uuid )
		assert result == sample_uuid_bytes
		assert len ( result ) == 16

	def test_to_1c_from_string ( self , sample_uuid_formatted ) :
		result = to_1c ( sample_uuid_formatted )
		assert len ( result ) == 16

	def test_to_1c_from_string_no_dashes ( self , sample_uuid_hex ) :
		result = to_1c ( sample_uuid_hex )
		assert len ( result ) == 16

	def test_roundtrip ( self , sample_uuid ) :
		"""UUID → 1С → UUID должно дать исходный."""
		result = from_1c ( to_1c ( sample_uuid ) )
		assert result == sample_uuid

	def test_generate_returns_uuid ( self ) :
		result = generate ( )
		assert isinstance ( result , UUID )

	def test_generate_unique ( self ) :
		uuids = { generate ( ) for _ in range ( 100 ) }
		assert len ( uuids ) == 100

	def test_format_uuid ( self , sample_uuid , sample_uuid_formatted ) :
		assert format_uuid ( sample_uuid ) == sample_uuid_formatted

	def test_format_uuid_from_hex ( self , sample_uuid_hex , sample_uuid_formatted ) :
		assert format_uuid ( sample_uuid_hex ) == sample_uuid_formatted

	def test_format_uuid_from_bytes ( self , sample_uuid_bytes , sample_uuid_formatted ) :
		assert format_uuid ( sample_uuid_bytes ) == sample_uuid_formatted

	def test_from_1c_invalid_length ( self ) :
		with pytest.raises ( ValueError ) :
			from_1c ( b'\x00' * 8 )

	@given ( st.binary ( min_size = 16 , max_size = 16 ) )
	def test_from_1c_hypothesis ( self , random_bytes ) :
		"""Property-based: from_1c всегда возвращает UUID для 16 байт."""
		result = from_1c ( random_bytes )
		assert isinstance ( result , UUID )

	@given ( st.uuids ( ) )
	def test_roundtrip_hypothesis ( self , uuid ) :
		"""Property-based: roundtrip для любых UUID."""
		result = from_1c ( to_1c ( uuid ) )
		assert result == uuid
