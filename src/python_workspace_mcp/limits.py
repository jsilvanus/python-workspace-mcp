from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ResourceLimits:
    """Execution limits applied to every workspace runtime."""

    cpu: float = 2.0
    memory_bytes: int = 4 * 1024 * 1024 * 1024
    storage_bytes: int = 10 * 1024 * 1024 * 1024
    execution_timeout_seconds: int = 60
    pids: int = 128
    max_output_bytes: int = 2 * 1024 * 1024
    max_artifacts_per_execution: int = 50

    def as_dict(self) -> dict:
        return {
            "cpu": self.cpu,
            "memory_bytes": self.memory_bytes,
            "storage_bytes": self.storage_bytes,
            "execution_timeout_seconds": self.execution_timeout_seconds,
            "pids": self.pids,
            "max_output_bytes": self.max_output_bytes,
            "max_artifacts_per_execution": self.max_artifacts_per_execution,
        }
