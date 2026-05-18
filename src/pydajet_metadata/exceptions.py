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


class VersionConflictError(Exception):
    """
    Конфликт версий при оптимистичной блокировке.

    Возникает, когда два пользователя пытаются изменить один объект.
    Поле _Version в 1С увеличивается при каждом изменении объекта.
    """

    pass


class MetadataOutdatedError(Exception):
    """
    Метаданные устарели — изменился корневой GUID конфигурации.

    В 1С каждый объект конфигурации имеет идентификатор версии метаданных.
    Если корневой файл (root) изменился — все объекты в памяти неактуальны.
    Требуется перезагрузка метаданных через Repository.
    """

    pass
