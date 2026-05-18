"""Интеграционные тесты независимости модулей."""
import os
import subprocess
import sys

import pytest


def _python_import_check(module_name: str, extra_path: str, remove_modules: list[str]) -> None:
    cmd = [
        sys.executable,
        "-c",
        "import os, sys; sys.path.insert(0, r'%s'); %s; print('ok')" % (
            extra_path,
            "; ".join([f"sys.modules.pop('{name}', None)" for name in remove_modules]),
        ),
    ]
    result = subprocess.run(
        cmd,
        cwd=os.getcwd(),
        env=os.environ.copy(),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())


def test_pydajet_metadata_imports_without_pydajet():
    src_path = os.path.join(os.getcwd(), "src")
    _python_import_check(
        "pydajet_metadata",
        src_path,
        ["pydajet", "pydajet.client", "pydajet_metadata"],
    )


def test_pydajet_does_not_import_pydajet_metadata():
    init_path = os.path.join(os.getcwd(), "src", "pydajet", "__init__.py")
    with open(init_path, "r", encoding="utf-8") as f:
        source = f.read()
    assert "pydajet_metadata" not in source
