"""Compatibility shim: provide `dajet.client.MetadataProvider` for tests.

This module intentionally proxies to `pydajet` so tests that patch
`dajet.client.MetadataProvider` still work.
"""
try:
    from pydajet import MetadataProvider  # type: ignore
except Exception:
    MetadataProvider = None
