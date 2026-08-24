from pathlib import Path

import pytest

from python_workspace_mcp.config import Settings
from python_workspace_mcp.users import UserManager
from python_workspace_mcp.workspaces import WorkspaceManager


def settings(tmp_path: Path, workspaces: str = "") -> Settings:
    return Settings(
        user_id="alice",
        user_name="Alice",
        workspace_path=tmp_path / "default",
        workspace_definitions=workspaces,
    )


def test_user_manager_returns_stable_identity(tmp_path: Path) -> None:
    manager = UserManager.from_settings(settings(tmp_path))
    assert manager.info() == {"id": "alice", "name": "Alice"}
    assert manager.current().id == "alice"
    assert manager.get("alice") == manager.current()


def test_workspace_defaults_to_configured_user(tmp_path: Path) -> None:
    manager = WorkspaceManager(settings(tmp_path))
    definition = manager.get_definition()
    assert definition.owner_user_id == "alice"


def test_workspace_can_explicitly_name_owner(tmp_path: Path) -> None:
    manager = WorkspaceManager(settings(tmp_path, "stats:Stats:/tmp/stats:alice"))
    assert manager.get_definition("stats").owner_user_id == "alice"


def test_unknown_user_is_rejected(tmp_path: Path) -> None:
    manager = UserManager.from_settings(settings(tmp_path))
    with pytest.raises(ValueError, match="Unknown user"):
        manager.get("bob")
