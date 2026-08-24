from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .limits import ResourceLimits


@dataclass(frozen=True)
class ResourceProfile:
    """A named resource policy with default and maximum execution limits."""

    id: str
    name: str
    defaults: ResourceLimits
    maximums: ResourceLimits

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "defaults": self.defaults.as_dict(),
            "maximums": self.maximums.as_dict(),
        }

    def validate(self, requested: ResourceLimits) -> ResourceLimits:
        """Validate an execution request and return the effective limits."""
        fields = (
            ("cpu", requested.cpu, self.maximums.cpu),
            ("memory_bytes", requested.memory_bytes, self.maximums.memory_bytes),
            ("storage_bytes", requested.storage_bytes, self.maximums.storage_bytes),
            ("execution_timeout_seconds", requested.execution_timeout_seconds, self.maximums.execution_timeout_seconds),
            ("pids", requested.pids, self.maximums.pids),
            ("max_output_bytes", requested.max_output_bytes, self.maximums.max_output_bytes),
            ("max_artifacts_per_execution", requested.max_artifacts_per_execution, self.maximums.max_artifacts_per_execution),
        )
        for name, value, maximum in fields:
            if value <= 0:
                raise ValueError(f"Resource {name} must be positive")
            if value > maximum:
                raise ValueError(f"Resource {name} exceeds profile maximum ({value} > {maximum})")
        return requested


def _profile(id: str, name: str, defaults: ResourceLimits, maximums: ResourceLimits) -> ResourceProfile:
    # A profile must never have defaults above its own maximums.
    ResourceProfile(id=id, name=name, defaults=defaults, maximums=maximums).validate(defaults)
    return ResourceProfile(id=id, name=name, defaults=defaults, maximums=maximums)


def builtin_profiles() -> dict[str, ResourceProfile]:
    return {
        "small": _profile(
            "small", "Small",
            ResourceLimits(cpu=1, memory_bytes=1 * 1024**3, storage_bytes=2 * 1024**3, execution_timeout_seconds=60, pids=64, max_output_bytes=1 * 1024**2, max_artifacts_per_execution=25),
            ResourceLimits(cpu=2, memory_bytes=2 * 1024**3, storage_bytes=5 * 1024**3, execution_timeout_seconds=180, pids=96, max_output_bytes=2 * 1024**2, max_artifacts_per_execution=50),
        ),
        "standard": _profile(
            "standard", "Standard",
            ResourceLimits(cpu=2, memory_bytes=4 * 1024**3, storage_bytes=10 * 1024**3, execution_timeout_seconds=300, pids=128, max_output_bytes=2 * 1024**2, max_artifacts_per_execution=50),
            ResourceLimits(cpu=4, memory_bytes=8 * 1024**3, storage_bytes=25 * 1024**3, execution_timeout_seconds=900, pids=256, max_output_bytes=4 * 1024**2, max_artifacts_per_execution=100),
        ),
        "large": _profile(
            "large", "Large",
            ResourceLimits(cpu=4, memory_bytes=16 * 1024**3, storage_bytes=50 * 1024**3, execution_timeout_seconds=900, pids=256, max_output_bytes=4 * 1024**2, max_artifacts_per_execution=100),
            ResourceLimits(cpu=8, memory_bytes=32 * 1024**3, storage_bytes=100 * 1024**3, execution_timeout_seconds=3600, pids=512, max_output_bytes=8 * 1024**2, max_artifacts_per_execution=250),
        ),
    }


def profile_from_dict(data: dict[str, Any]) -> ResourceProfile:
    def limits(key: str) -> ResourceLimits:
        value = data[key]
        return ResourceLimits(**value)

    profile = ResourceProfile(id=str(data["id"]), name=str(data["name"]), defaults=limits("defaults"), maximums=limits("maximums"))
    profile.validate(profile.defaults)
    return profile
