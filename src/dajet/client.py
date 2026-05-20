"""Compatibility shim: provide `dajet.client.MetadataProvider` for tests."""

from __future__ import annotations

from pydajet._dotnet import MetadataProviderType

MetadataProvider: MetadataProviderType
try:
    from pydajet import MetadataProvider as _MetadataProvider

    MetadataProvider = _MetadataProvider
except Exception:
    MetadataProvider = None
