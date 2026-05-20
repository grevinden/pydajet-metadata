"""Протоколы для объектов DaJet / .NET (pythonnet)."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import TYPE_CHECKING, Protocol, runtime_checkable


@runtime_checkable
class DotNetGuidList(Protocol):
    def Add(self, item: object) -> None: ...

    @property
    def Count(self) -> int: ...

    def __getitem__(self, index: int) -> str: ...


@runtime_checkable
class DotNetMetadataColumn(Protocol):
    @property
    def Name(self) -> str: ...

    @property
    def Type(self) -> object | None: ...


@runtime_checkable
class DotNetColumnCollection(Protocol):
    @property
    def Count(self) -> int: ...

    def __iter__(self) -> Iterator[DotNetMetadataColumn]: ...


@runtime_checkable
class DotNetMetadataProperty(Protocol):
    @property
    def Name(self) -> str: ...

    @property
    def Columns(self) -> DotNetColumnCollection | None: ...


@runtime_checkable
class DotNetEntityCollection(Protocol):
    @property
    def Count(self) -> int: ...

    def __iter__(self) -> Iterator[DotNetEntity]: ...


@runtime_checkable
class DotNetPropertyCollection(Protocol):
    def __iter__(self) -> Iterator[DotNetMetadataProperty]: ...


@runtime_checkable
class DotNetEntity(Protocol):
    @property
    def Name(self) -> str: ...

    @property
    def DbName(self) -> str: ...

    @property
    def Properties(self) -> DotNetPropertyCollection | None: ...

    @property
    def Entities(self) -> DotNetEntityCollection | None: ...


@runtime_checkable
class DotNetMetadataIndex(Protocol):
    @property
    def Keys(self) -> Iterable[object]: ...

    def __getitem__(self, key: object) -> object: ...


@runtime_checkable
class DotNetConfiguration(Protocol):
    @property
    def Name(self) -> str: ...

    @property
    def Alias(self) -> str | None: ...

    @property
    def Metadata(self) -> DotNetMetadataIndex: ...


@runtime_checkable
class DotNetMetadataProviderClass(Protocol):
    @staticmethod
    def Create(data_source: object, connection_string: str) -> object: ...


@runtime_checkable
class DotNetMetadataProvider(Protocol):
    @property
    def PlatformVersion(self) -> int: ...

    def GetConfigurations(self) -> object: ...

    def ResolveReferences(self, entity_list: DotNetGuidList) -> object: ...

    def GetMetadataObject(self, name: str) -> object: ...


@runtime_checkable
class DotNetDataSourceType(Protocol):
    PostgreSql: object
    SqlServer: object


if TYPE_CHECKING:
    from DaJet.Data import DataSourceType as _DataSourceTypeCls
    from DaJet.Metadata import MetadataProvider as _MetadataProviderCls
    from System import Guid as _GuidCls
    from System.Collections.Generic import List as _ListCls

    MetadataProviderType = type[_MetadataProviderCls] | None
    DataSourceTypeType = type[_DataSourceTypeCls] | None
    GuidType = type[_GuidCls] | None
    GenericListType = type[_ListCls] | None
else:
    MetadataProviderType = type[DotNetMetadataProviderClass] | None
    DataSourceTypeType = type[DotNetDataSourceType] | None
    GuidType = type[object] | None
    GenericListType = type[object] | None
