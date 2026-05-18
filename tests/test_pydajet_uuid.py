import importlib.util
import pytest
from uuid import UUID
from pathlib import Path


_UUID_PATH = Path(__file__).parent.parent / "src" / "pydajet" / "_uuid.py"


def _load_uuid_module():
    spec = importlib.util.spec_from_file_location("pydajet_uuid_test", str(_UUID_PATH))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_from_and_to_1c_roundtrip():
    mod = _load_uuid_module()
    u = mod.generate()
    b = mod.to_1c(u)
    u2 = mod.from_1c(b)
    assert isinstance(u2, UUID)
    assert str(u2) == str(u)


def test_to_1c_accepts_string_and_bytes():
    mod = _load_uuid_module()
    u = mod.generate()
    s = str(u)
    b_from_str = mod.to_1c(s)
    assert isinstance(b_from_str, bytes)
    b_from_uuid = mod.to_1c(u)
    assert b_from_uuid == b_from_str


def test_from_1c_invalid_length():
    mod = _load_uuid_module()
    with pytest.raises(ValueError):
        mod.from_1c(b"short")


def test_format_uuid_variants():
    mod = _load_uuid_module()
    u = mod.generate()
    s = mod.format_uuid(u)
    assert isinstance(s, str) and len(s) == 36
    s2 = mod.format_uuid(str(u))
    assert s2 == s
    # bytes in 1c format
    b = mod.to_1c(u)
    s3 = mod.format_uuid(b)
    assert s3 == s
