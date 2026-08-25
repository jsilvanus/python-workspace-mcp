from __future__ import annotations

import mimetypes
import subprocess
import time
import uuid
from pathlib import Path
from threading import RLock
from typing import Protocol

from .limits import ResourceLimits
from .workspace import Workspace


class ExecutionBackend(Protocol):
    def execute(self, code: str, limits: ResourceLimits | None = None) -> dict: ...
    def execute_file(self, path: str, limits: ResourceLimits | None = None) -> dict: ...


class DockerExecutionError(RuntimeError):
    pass


class ResourceLimitError(RuntimeError):
    pass


class DockerExecutionBackend:
    """Docker execution with a dedicated container and per-workspace limits."""

    def __init__(self, *, image: str, container_name: str, workspace: Workspace, limits: ResourceLimits) -> None:
        self.image = image
        self.container_name = container_name
        self.workspace = workspace
        self.limits = limits
        self._lock = RLock()

    def _docker(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["docker", *args], capture_output=True, text=True, check=check)

    def ensure_container(self, limits: ResourceLimits | None = None) -> None:
        limits = limits or self.limits
        inspect = self._docker("inspect", "-f", "{{.State.Running}}", self.container_name, check=False)
        if inspect.returncode == 0:
            if inspect.stdout.strip().lower() != "true":
                started = self._docker("start", self.container_name, check=False)
                if started.returncode != 0:
                    raise DockerExecutionError(started.stderr.strip() or "Could not start runtime container")
            self._update_container_limits(limits)
            return
        args = [
            "run", "-d", "--name", self.container_name,
            "--user", "1000:1000", "--cpus", str(limits.cpu),
            "--memory", str(limits.memory_bytes), "--memory-swap", str(limits.memory_bytes),
            "--pids-limit", str(limits.pids), "--network", "none", "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges:true", "--read-only",
            "--tmpfs", "/tmp:rw,nosuid,nodev,size=256m", "-e", "HOME=/tmp",
            "-e", "MPLCONFIGDIR=/tmp/matplotlib", "-v", f"{self.workspace.root}:/workspace:rw",
            "-w", "/workspace", self.image, "sleep", "infinity",
        ]
        created = self._docker(*args, check=False)
        if created.returncode != 0:
            raise DockerExecutionError(created.stderr.strip() or "Could not create runtime container")

    def _update_container_limits(self, limits: ResourceLimits) -> None:
        updated = self._docker("update", "--cpus", str(limits.cpu), "--memory", str(limits.memory_bytes), "--memory-swap", str(limits.memory_bytes), "--pids-limit", str(limits.pids), self.container_name, check=False)
        if updated.returncode != 0:
            raise DockerExecutionError(updated.stderr.strip() or "Could not update runtime limits")

    def _run(self, command: list[str], limits: ResourceLimits, execution_id: str) -> dict:
        self._check_storage(limits)
        self.ensure_container(limits)
        before = self._snapshot_files()
        started_at = time.time()
        started = time.monotonic()
        result = subprocess.run(["docker", "exec", self.container_name, "timeout", "--signal=KILL", f"{limits.execution_timeout_seconds}s", *command], capture_output=True, text=True)
        finished_at = time.time()
        duration = time.monotonic() - started
        after = self._snapshot_files()
        before_paths = set(before)
        after_paths = set(after)
        created = sorted(after_paths - before_paths)
        deleted = sorted(before_paths - after_paths)
        modified = sorted(path for path in before_paths & after_paths if before[path] != after[path])
        changed = created + modified
        timed_out = result.returncode in (124, 137)
        storage_used = self._storage_used()
        storage_exceeded = storage_used > limits.storage_bytes
        output_limited = len(result.stdout.encode()) + len(result.stderr.encode()) > limits.max_output_bytes
        stdout = _truncate(result.stdout, limits.max_output_bytes // 2)
        stderr = _truncate(result.stderr, limits.max_output_bytes // 2)
        if storage_exceeded:
            stderr += "\nWorkspace storage limit exceeded."
        if output_limited:
            stderr += "\nExecution output was truncated."
        artifacts = [self._artifact(path) for path in changed[: limits.max_artifacts_per_execution] if (self.workspace.root / path).is_file()]
        return {
            "execution_id": execution_id,
            "workspace_id": self.workspace.id,
            "success": result.returncode == 0 and not storage_exceeded,
            "exit_code": result.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "duration_seconds": round(duration, 3),
            "started_at": started_at,
            "finished_at": finished_at,
            "timed_out": timed_out,
            "resource_limits": limits.as_dict(),
            "storage_used_bytes": storage_used,
            "files": {"created": created, "modified": modified, "deleted": deleted},
            "artifacts": artifacts,
            "artifacts_truncated": len(changed) > len(artifacts),
        }

    def execute(self, code: str, limits: ResourceLimits | None = None) -> dict:
        limits = limits or self.limits
        with self._lock:
            return self._run(["python", "-c", code], limits, f"exec_{uuid.uuid4().hex}")

    def execute_file(self, path: str, limits: ResourceLimits | None = None) -> dict:
        limits = limits or self.limits
        with self._lock:
            target = self.workspace.resolve(path)
            if not target.is_file():
                raise ValueError(f"Not a file: {path}")
            if target.suffix.lower() != ".py":
                raise ValueError("execute_file only accepts .py files")
            relative = target.relative_to(self.workspace.root).as_posix()
            return self._run(["python", relative], limits, f"exec_{uuid.uuid4().hex}")

    def _storage_used(self) -> int:
        return sum(path.stat().st_size for path in self.workspace.root.rglob("*") if path.is_file()) if self.workspace.root.exists() else 0

    def _check_storage(self, limits: ResourceLimits) -> None:
        if self._storage_used() > limits.storage_bytes:
            raise ResourceLimitError("Workspace storage limit already exceeded")

    def _snapshot_files(self) -> dict[str, tuple[int, int]]:
        files: dict[str, tuple[int, int]] = {}
        if self.workspace.root.exists():
            for path in self.workspace.root.rglob("*"):
                if path.is_file():
                    stat = path.stat()
                    files[path.relative_to(self.workspace.root).as_posix()] = (stat.st_size, stat.st_mtime_ns)
        return files

    def _artifact(self, relative_path: str) -> dict:
        path = self.workspace.root / relative_path
        return {"path": relative_path, "size_bytes": path.stat().st_size, "mime_type": _mime_type(path)}


def _truncate(value: str, max_bytes: int) -> str:
    encoded = value.encode()
    return value if len(encoded) <= max_bytes else encoded[:max_bytes].decode(errors="replace") + "\n[output truncated]"


def _mime_type(path: Path) -> str:
    return mimetypes.guess_type(path.name)[0] or "application/octet-stream"
