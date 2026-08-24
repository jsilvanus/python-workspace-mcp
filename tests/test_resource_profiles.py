from pathlib import Path

import pytest

from python_workspace_mcp.config import Settings
from python_workspace_mcp.limits import ResourceLimits
from python_workspace_mcp.profiles import ResourceProfileManager
from python_workspace_mcp.workspaces import WorkspaceManager


def settings(tmp_path: Path) -> Settings:
    return Settings(state_path=tmp_path / "state.json", workspace_path=tmp_path / "default")


def test_builtin_profiles_are_available(tmp_path: Path):
    manager = ResourceProfileManager(settings(tmp_path))
    profile = manager.get("standard")
    assert profile.defaults.memory_bytes == 4 * 1024**3
    assert profile.maximums.memory_bytes == 8 * 1024**3
    assert profile.capabilities.package_install is True
    assert profile.capabilities.outbound_network is False


def test_small_profile_disables_package_install(tmp_path: Path):
    assert ResourceProfileManager(settings(tmp_path)).get("small").capabilities.package_install is False


def test_profile_rejects_request_above_maximum(tmp_path: Path):
    manager = ResourceProfileManager(settings(tmp_path))
    profile = manager.get("standard")
    requested = ResourceLimits(cpu=5, memory_bytes=profile.defaults.memory_bytes, storage_bytes=profile.defaults.storage_bytes, execution_timeout_seconds=profile.defaults.execution_timeout_seconds, pids=profile.defaults.pids, max_output_bytes=profile.defaults.max_output_bytes, max_artifacts_per_execution=profile.defaults.max_artifacts_per_execution)
    with pytest.raises(ValueError, match="exceeds profile maximum"):
        profile.validate(requested)


def test_workspace_selects_profile(tmp_path: Path):
    cfg = settings(tmp_path)
    manager = WorkspaceManager(cfg)
    definition = manager.create_workspace("alice", "Alice", tmp_path / "alice", "default", "small")
    assert definition.profile_id == "small"
    assert definition.capabilities.package_install is False
