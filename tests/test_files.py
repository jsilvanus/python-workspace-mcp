from pathlib import Path

import pytest

from python_workspace_mcp.files import FileManager
from python_workspace_mcp.workspace import Workspace


def manager(tmp_path: Path) -> FileManager:
    root = tmp_path / "workspace"
    root.mkdir()
    return FileManager(Workspace(id="ws1", name="Test", root=root))


def test_file_ids_are_stable_and_scoped(tmp_path: Path):
    fm = manager(tmp_path)
    (fm.root / "hello.txt").write_text("hello", encoding="utf-8")
    record = fm.list()[0]
    assert record.id.startswith("file_")
    assert fm.resolve_id(record.id)[0] == record


def test_read_file_by_id(tmp_path: Path):
    fm = manager(tmp_path)
    (fm.root / "hello.txt").write_text("hello", encoding="utf-8")
    record = fm.list()[0]
    assert fm.read_text(record.id) == "hello"


def test_path_traversal_is_rejected(tmp_path: Path):
    fm = manager(tmp_path)
    with pytest.raises(ValueError, match="escapes workspace"):
        fm._safe_path("../outside.txt")
