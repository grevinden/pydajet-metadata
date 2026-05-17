# tests/test_conftest.py
def test_fixtures(sample_connection_string, sample_uuid, sample_column_map):
    """Проверяет, что фикстуры работают."""
    assert "Host=localhost" in sample_connection_string
    assert str(sample_uuid) == "9c280050-b666-dffa-11f1-4e880e761abe"
    assert "Наименование" in sample_column_map
