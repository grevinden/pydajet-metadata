"""Пользовательские исключения для слоя метаданных."""


class MetadataError(Exception):
    """Базовое исключение для ошибок метаданных."""

    pass


class MetadataNotFoundError(MetadataError):
    """Объект метаданных не найден."""

    pass


class MetadataNotImplementedError(MetadataError):
    """Функциональность не реализована для данного типа объекта."""

    pass


class DotNetRuntimeError(MetadataError):
    """Ошибка инициализации .NET Runtime."""

    pass
