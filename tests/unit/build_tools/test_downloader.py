from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.build_tools.config import BuildConfig
from scripts.build_tools.downloader import DownloadTask, FileDownloader


def test_file_downloader_retries_and_uses_temp_file(tmp_path: Path):
    config = BuildConfig(root_path=tmp_path)
    downloader = FileDownloader(config)
    destination = tmp_path / "artifact.zip"
    temp_path = destination.with_suffix(destination.suffix + ".part")

    call_count = {"count": 0}

    def fake_download_once(url, dest, temp, initial_size):
        call_count["count"] += 1
        if call_count["count"] == 1:
            raise RuntimeError("temporary network error")
        dest.write_bytes(b"content")
        return dest

    with patch.object(FileDownloader, "_download_once", side_effect=fake_download_once):
        result = downloader.download(DownloadTask(url="https://example.com/file", destination=destination), retries=2)

    assert result == destination
    assert destination.exists()
    assert destination.read_bytes() == b"content"
    assert not temp_path.exists()


def test_file_downloader_cleans_temp_file_on_final_failure(tmp_path: Path):
    config = BuildConfig(root_path=tmp_path)
    downloader = FileDownloader(config)
    destination = tmp_path / "artifact.zip"
    temp_path = destination.with_suffix(destination.suffix + ".part")

    def fake_download_once(url, dest, temp, initial_size):
        temp.write_bytes(b"partial")
        raise RuntimeError("permanent failure")

    with patch.object(FileDownloader, "_download_once", side_effect=fake_download_once):
        with pytest.raises(RuntimeError, match="permanent failure"):
            downloader.download(DownloadTask(url="https://example.com/file", destination=destination), retries=2)

    assert not temp_path.exists()
    assert not destination.exists()
