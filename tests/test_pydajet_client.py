import importlib
import sys
import types
from types import SimpleNamespace

import pytest

from pydajet_metadata.exceptions import MetadataError, MetadataNotImplementedError


class FakeList(list):
    def __init__(self):
        super().__init__()

    @property
    def Count(self):
        return len(self)

    def Add(self, v):
        self.append(v)


class FakeNames(list):
    @property
    def Count(self):
        return len(self)


class FakeProvider:
    def __init__(self, config):
        self._config = config

    def GetConfigurations(self):
        return [self._config]

    def ResolveReferences(self, entity_list):
        # return names, _
        names = FakeNames([self._config._names.get(i, None) for i in range(len(entity_list))])
        return names, None

    def GetMetadataObject(self, name):
        if name == "raise_not_impl":
            raise NotImplementedError("not implemented")
        if name == "raise_attr":
            raise AttributeError("not found")
        if name == "raise_other":
            raise RuntimeError("boom")
        return SimpleNamespace(
            DbName="_Table",
            Properties=[SimpleNamespace(Name="id", Columns=FakeNames([SimpleNamespace(Name="_idrref", Type="bytea")])), SimpleNamespace(Name="name", Columns=FakeNames([SimpleNamespace(Name="name", Type="varchar")]))],
            Entities=FakeNames([SimpleNamespace(Name='tabular', DbName='_Tab', Properties=FakeNames([]))]),
        )


class FakeMetadata:
    def __init__(self, metadata_map):
        self._metadata_map = metadata_map

    @property
    def Keys(self):
        return list(self._metadata_map.keys())

    def __getitem__(self, key):
        return self._metadata_map[key]


class FakeConfig:
    def __init__(self, metadata_map, name="Cfg", alias=None):
        self.Metadata = FakeMetadata(metadata_map)
        self.Name = name
        self.Alias = alias
        # map index to name
        self._names = {}


class FakeMetadataProvider:
    @staticmethod
    def Create(ds, cs):
        # return (provider,)
        # Build config where Metadata is dict-like with Keys attribute
        metadata = {"t1": [1, 2], "t2": []}
        config = FakeConfig(metadata)
        # set names mapping used in ResolveReferences
        config._names = {0: 'Справочник.Тест', 1: 'Документ.Тест2'}
        provider = FakeProvider(config)
        return (provider,)


def import_client_with_fakes():
    # Insert fake pydajet module to avoid real .NET imports
    fake = types.ModuleType("pydajet")
    # Mark as package so submodule imports like pydajet.client work
    fake.__path__ = []
    class DS:
        PostgreSql = 1
        SqlServer = 2
    fake.DataSourceType = DS
    fake.Guid = int
    fake.List = FakeList
    fake.MetadataProvider = FakeMetadataProvider
    # ensure exception names available in builtins for raises
    import builtins
    builtins.MetadataNotImplementedError = MetadataNotImplementedError
    builtins.MetadataError = MetadataError

    sys.modules["pydajet"] = fake
    # Load pydajet.client from file to avoid package import issues.
    import importlib.util
    from pathlib import Path

    client_path = Path(__file__).resolve().parents[1] / "src" / "pydajet" / "client.py"
    spec = importlib.util.spec_from_file_location("pydajet.client", str(client_path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["pydajet.client"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_type_by_prefix_and_list_types_and_objects():
    mod = import_client_with_fakes()
    cls = mod.MetadataClient
    # _type_by_prefix
    assert cls._type_by_prefix("Справочник.Whatever") == "Справочники"
    assert cls._type_by_prefix("Unknown.X") == "Неизвестный"

    mc = cls("conn://x")
    # list_types returns unique types
    types_list = mc.list_types()
    assert isinstance(types_list, list)
    # list_objects for 'Справочники' should return entries
    objs = mc.list_objects("Справочники")
    assert isinstance(objs, list)
    if objs:
        obj = objs[0]
        assert "name" in obj and "table" in obj and "properties" in obj and "children" in obj


def test_get_entity_exceptions():
    mod = import_client_with_fakes()
    cls = mod.MetadataClient
    mc = cls("conn://x")
    # provider configured in FakeMetadataProvider
    # NotImplementedError should raise MetadataNotImplementedError
    with pytest.raises(MetadataNotImplementedError):
        mc._get_entity("raise_not_impl")
    # AttributeError should return None
    assert mc._get_entity("raise_attr") is None
    # Other exception should raise MetadataError
    with pytest.raises(MetadataError):
        mc._get_entity("raise_other")


def test_find_binary_folder(monkeypatch):
    import importlib.util
    from pathlib import Path

    platform_path = Path(__file__).resolve().parents[1] / "src" / "pydajet" / "_platform.py"
    spec = importlib.util.spec_from_file_location("pydajet._platform", str(platform_path))
    platform_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(platform_mod)

    monkeypatch.setattr(platform_mod.platform, "system", lambda: "Windows")
    monkeypatch.setattr(platform_mod.platform, "machine", lambda: "AMD64")

    path = platform_mod.find_binary_folder()
    assert path.name == "win-x64"
    assert path.exists()


def test_pydajet_package_import_without_dotnet(monkeypatch, tmp_path):
    fake_binary_folder = tmp_path
    (fake_binary_folder / "DaJet.Metadata.runtimeconfig.json").write_text("{}")

    sys.modules.pop('pydajet', None)
    sys.modules.pop('pydajet.client', None)
    sys.modules.pop('pydajet._platform', None)
    sys.modules.pop('pydajet._uuid', None)

    fake_platform = types.ModuleType('pydajet._platform')
    fake_platform.find_binary_folder = lambda: fake_binary_folder
    monkeypatch.setitem(sys.modules, 'pydajet._platform', fake_platform)

    fake_clr = types.SimpleNamespace(AddReference=lambda *args, **kwargs: None)
    monkeypatch.setitem(sys.modules, 'clr', fake_clr)

    dajet_module = types.ModuleType('DaJet')
    dajet_module.__path__ = []
    monkeypatch.setitem(sys.modules, 'DaJet', dajet_module)

    dajet_metadata = types.ModuleType('DaJet.Metadata')
    dajet_metadata.MetadataProvider = types.SimpleNamespace(Create=lambda ds, cs: (types.SimpleNamespace(GetConfigurations=lambda: [types.SimpleNamespace(Metadata=types.SimpleNamespace(Keys=[]), Name='Cfg', Alias='Alias')]),))
    monkeypatch.setitem(sys.modules, 'DaJet.Metadata', dajet_metadata)

    dajet_data = types.ModuleType('DaJet.Data')
    dajet_data.DataSourceType = types.SimpleNamespace(PostgreSql=1, SqlServer=2)
    monkeypatch.setitem(sys.modules, 'DaJet.Data', dajet_data)

    system_module = types.ModuleType('System')
    system_module.__path__ = []
    system_module.Guid = int
    monkeypatch.setitem(sys.modules, 'System', system_module)

    system_collections = types.ModuleType('System.Collections')
    system_collections.__path__ = []
    monkeypatch.setitem(sys.modules, 'System.Collections', system_collections)

    system_generic = types.ModuleType('System.Collections.Generic')
    system_generic.List = list
    monkeypatch.setitem(sys.modules, 'System.Collections.Generic', system_generic)

    from pathlib import Path
    import importlib.util

    init_path = Path(__file__).resolve().parents[1] / "src" / "pydajet" / "__init__.py"
    spec = importlib.util.spec_from_file_location("pydajet", str(init_path))
    pydajet_pkg = importlib.util.module_from_spec(spec)
    pydajet_pkg.__path__ = [str(init_path.parent)]
    monkeypatch.setitem(sys.modules, 'pydajet', pydajet_pkg)

    spec.loader.exec_module(pydajet_pkg)

    assert pydajet_pkg.PATH_BIN == fake_binary_folder
    assert hasattr(pydajet_pkg, 'MetadataClient')
    assert pydajet_pkg.DataSourceType.PostgreSql == 1
    assert pydajet_pkg.Guid is int
