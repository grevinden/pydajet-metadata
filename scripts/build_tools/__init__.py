"""Build tooling for setup.py orchestration."""

from __future__ import annotations

__all__ = [
    "DownloadCommand",
    "EggInfoWithDownload",
    "download_all_binaries",
]


def __getattr__(name: str):
    if name in __all__:
        from .commands import DownloadCommand, EggInfoWithDownload, download_all_binaries

        exports = {
            "DownloadCommand": DownloadCommand,
            "EggInfoWithDownload": EggInfoWithDownload,
            "download_all_binaries": download_all_binaries,
        }
        return exports[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
