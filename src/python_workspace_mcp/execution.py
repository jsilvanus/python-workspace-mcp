from __future__ import annotations

import subprocess
import time
from pathlib import Path

from .config import Settings
from .workspace import Workspace


class DockerExecutionError(RuntimeError):
    pass


class DockerExecutionBackend:
    """Phase 1 execution backend: one persistent Docker container per server."""

    def __init__(self, settings: Settings, workspace: Workspace) -> None:
        self.settings = settings
        self.workspace = workspace

    def _docker(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["docker", *args],
            capture_output=True,
            text=True,
            check=check,
        )

    def ensure_container(self) -> None:
        inspect = self._docker("inspect", "-f", "{{.State.Running}}", self.settings.docker_container, check=False)
        if inspect.returncode == 0:
            if inspect.stdout.strip().lower() != "true":
                started = self._docker("start", self.settings.docker_container, check=False)
                if started.returncode != 0:
                    raise DockerExecutionError(started.stderr.strip() or "Could not start runtime container")
            return

        created = self._docker(
            "run", "-d",
            "--name", self.settings.docker_container,
            "--user", "1000:1000",
            "-v", f"{self.workspace.root}:/workspace",
            self.settings.docker_image,
            "sleep", "infinity",
            check=False,
        )
        if created.returncode != 0:
            raise DockerExecutionError(created.stderr.strip() or "Could not create runtime container")

    def execute(self, code: str) -> dict:
        self.ensure_container()
        before = self._files()
        started = time.monotonic()
        result = subprocess.run(
            [
                "docker", "exec", self.settings.docker_container,
                "timeout", "--signal=KILL", f"{self.settings.execution_timeout}s",
                "python", "-c", code,
            ],
            capture_output=True,
            text=True,
        )
        duration = time.monotonic() - started
        after = self._files()
        changed = sorted(after - before)
        timed_out = result.returncode == 137

        return {
            "success": result.returncode == 0,
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "duration_seconds": round(duration, 3),
            "timed_out": timed_out,
            "artifacts": [self._artifact(path) for path in changed],
        }

    def _files(self) -> set[str]:
        files: set[str] = set()
        for path in self.workspace.root.rglob("*"):
            if path.is_file():
                files.add(path.relative_to(self.workspace.root).as_posix())
        return files

    def _artifact(self, relative_path: str) -> dict:
        path = self.workspace.root / relative_path
        return {
            "path": relative_path,
            "size_bytes": path.stat().st_size,
            "mime_type": _mime_type(path),
        }


def _mime_type(path: Path) -> str:
    import mimetypes

    return mimetypes.guess_type(path.name)[0] or "application/octet-stream"
