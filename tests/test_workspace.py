from pathlib import Path

import pytest

from python_workspace_mcp.workspace import Workspace


def test_resolve_stays_inside_workspace(tmp_path: Path):
    workspace = Workspace("default", "Default", tmp_path)
    assert workspace.resolve("data/file.csv") == tmp_path / "data/file.csv"


def test_resolve_rejects_escape(tmp_path: Path):
    workspace = Workspace("default", "Default", tmp_path)
    with pytest.raises(ValueError):
        workspace.resolve("../../outside.txt")
