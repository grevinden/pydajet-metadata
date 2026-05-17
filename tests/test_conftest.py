def test_fixtures(sample_connection_string, sample_uuid, sample_column_map):
    """Проверяет, что фикстуры работают."""
    assert "Host=localhost" in sample_connection_string
    assert str(sample_uuid) == "5000289c-66b6-fadf-11f1-4e880e761abe"  # исправлено
    assert "Наименование" in sample_column_map
