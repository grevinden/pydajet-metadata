import json
import platform
import subprocess
from pathlib import Path


class DaJetMetadata:
    def __init__(self):
        self.binary_path = self._find_binary()
        if not self.binary_path.exists():
            raise FileNotFoundError(f"Binary not found: {self.binary_path}")

    @staticmethod
    def _find_binary() -> Path:
        system = platform.system().lower()
        machine = platform.machine().lower()

        os_map = {"windows": "win", "linux": "linux", "darwin": "osx"}
        os_name = os_map[system]
        arch = "x64" if machine in ("x86_64", "amd64") else "arm64"

        folder = f"{os_name}-{arch}"  # ← просто win-x64, без префикса
        exe = "DaJet.Metadata.exe" if system == "windows" else "DaJet.Metadata"

        return Path(__file__).parent / "bin" / folder / exe

    def _run(self, *args):
        return subprocess.run(
            [str(self.binary_path)] + list(args),
            capture_output=True, text=True, timeout=300
        )

    def read_metadata(self, connection_string: str) -> dict:
        result = self._run("--connection", connection_string, "--format", "json")
        if result.returncode != 0:
            raise RuntimeError(f"Error: {result.stderr}")
        return json.loads(result.stdout)
