"""UUID utilities для модуля pydajet."""
from uuid import UUID, uuid4


def from_1c(uuid_bytes: bytes) -> UUID:
    """Преобразует 16 байт из формата 1С в стандартный UUID."""
    if len(uuid_bytes) != 16:
        raise ValueError(f"Expected 16 bytes, got {len(uuid_bytes)}")
    d = list(uuid_bytes)
    return UUID(bytes=bytes([d[3], d[2], d[1], d[0], d[5], d[4], d[7], d[6], *d[8:16]]))


def to_1c(uuid: UUID | str | bytes) -> bytes:
    """Преобразует UUID (или строку/байты) в 1С-формат."""
    if isinstance(uuid, str):
        uuid = UUID(uuid.replace('-', ''))
    elif isinstance(uuid, bytes):
        uuid = UUID(bytes=uuid)
    d = list(uuid.bytes)
    return bytes([d[3], d[2], d[1], d[0], d[5], d[4], d[7], d[6], *d[8:16]])


def generate() -> UUID:
    """Генерирует новый стандартный UUID."""
    return uuid4()


def format_uuid(uuid: UUID | str | bytes) -> str:
    """Возвращает строковое представление UUID в стандартном формате."""
    if isinstance(uuid, str):
        return str(UUID(uuid.replace('-', '')))
    if isinstance(uuid, bytes):
        return str(from_1c(uuid))
    return str(uuid)
