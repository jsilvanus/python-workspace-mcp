from pathlib import Path

import pytest

from python_workspace_mcp.config import Settings
from python_workspace_mcp.execution import _truncate
from python_workspace_mcp.limits import ResourceLimits
from python_workspace_mcp.workspaces import WorkspaceManager


def test_default_manager_has_one_workspace(tmp_path: Path):
    settings = Settings(workspace_path=tmp_path, state_path=tmp_path / "state.json")
    manager = WorkspaceManager(settings)
    assert manager.ids() == ["default"]
    assert manager.info()["id"] == "default"


def test_manager_loads_multiple_workspaces(tmp_path: Path):
    settings = Settings(
        default_workspace_id="stats",
        workspace_definitions=(
            f"stats:Statistics:{tmp_path / 'stats'},sim:Simulation:{tmp_path / 'sim'}"
        ),
        state_path=tmp_path / "state.json",
    )
    manager = WorkspaceManager(settings)
    assert manager.ids() == ["stats", "sim"]
    assert manager.get("stats").root == (tmp_path / "stats").resolve()
    assert manager.get("sim").root == (tmp_path / "sim").resolve()


def test_manager_rejects_invalid_workspace_id(tmp_path: Path):
    settings = Settings(
        workspace_definitions=f"../bad:Bad:{tmp_path / 'bad'}",
        state_path=tmp_path / "state.json",
    )
    with pytest.raises(ValueError):
        WorkspaceManager(settings)


def test_manager_rejects_unknown_workspace(tmp_path: Path):
    manager = WorkspaceManager(Settings(workspace_path=tmp_path, state_path=tmp_path / "state.json"))
    with pytest.raises(ValueError):
        manager.get("missing")


def test_manager_rejects_default_not_configured(tmp_path: Path):
    settings = Settings(
        default_workspace_id="missing",
        workspace_definitions=f"stats:Statistics:{tmp_path / 'stats'}",
        state_path=tmp_path / "state.json",
    )
    with pytest.raises(ValueError):
        WorkspaceManager(settings)


def test_phase2_limits_have_safe_defaults():
    limits = ResourceLimits()
    assert limits.cpu == 2.0
    assert limits.memory_bytes == 4 * 1024 * 1024 * 1024
    assert limits.pids == 128
    assert limits.storage_bytes == 10 * 1024 * 1024 * 1024


def test_output_truncation():
    assert _truncate("abcdef", 3).startswith("abc")
    assert "output truncated" in _truncate("abcdef", 3)
