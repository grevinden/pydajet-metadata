import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.build_tools.commands import download_all_binaries, download_platform
from scripts.build_tools.config import BuildConfig


def test_download_all_binaries_skips_when_release_unchanged(tmp_path: Path):
    config = BuildConfig(root_path=tmp_path)
    for platform in config.platforms:
        (config.bin_dir / platform).mkdir(parents=True, exist_ok=True)

    config.state_file.parent.mkdir(parents=True, exist_ok=True)
    config.state_file.write_text(json.dumps({"published_at": "2026-01-01T00:00:00Z", "assets": []}), "utf-8")
    for platform in config.platforms:
        (config.bin_dir / platform / "marker").write_text("ok", "utf-8")

    with patch("scripts.build_tools.commands.is_release_changed", return_value=False) as changed_mock:
        with patch("scripts.build_tools.commands.read_dajet_version", return_value="v1.0.0"):
            with patch("scripts.build_tools.commands.get_remote_release_state", return_value=None):
                result = download_all_binaries(config)

    assert result is config
    changed_mock.assert_called_once_with(config)


def test_download_all_binaries_force_triggers_download(tmp_path: Path):
    config = BuildConfig(root_path=tmp_path)
    for platform in config.platforms:
        (config.bin_dir / platform).mkdir(parents=True, exist_ok=True)

    with patch("scripts.build_tools.commands.is_release_changed", return_value=False):
        with patch("scripts.build_tools.commands.read_dajet_version", return_value="v1.0.0"):
            with patch("scripts.build_tools.commands.get_remote_release_state", return_value={"published_at": "x", "assets": []}):
                with patch("scripts.build_tools.commands.download_platform", return_value="win-x64") as download_mock:
                    result = download_all_binaries(config, force=True)

    assert result is config
    assert download_mock.call_count == len(config.platforms)


def test_download_platform_cleans_failed_destination(tmp_path: Path):
    config = BuildConfig(root_path=tmp_path)
    version = "v1"
    platform_name = "win-x64"
    archive_path = config.cache_path / f"dajet-metadata-{platform_name}.zip"
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    archive_path.write_bytes(b"dummy archive")

    def fake_download(task):
        return archive_path

    with patch("scripts.build_tools.commands.FileDownloader.download", side_effect=fake_download):
        with patch("scripts.archive.ArchiveExtractor.extract_all", side_effect=RuntimeError("bad archive")):
            with pytest.raises(RuntimeError, match="bad archive"):
                download_platform(config, version, platform_name)

    assert not (config.bin_dir / platform_name).exists()
