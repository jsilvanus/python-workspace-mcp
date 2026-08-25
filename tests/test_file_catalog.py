from pathlib import Path

from python_workspace_mcp.files import FileCatalog
from python_workspace_mcp.workspace import Workspace


def test_catalog_assigns_stable_ids_and_indexes_paths(tmp_path: Path):
    workspace = Workspace(id="ws", name="Workspace", root=tmp_path / "workspace")
    workspace.root.mkdir()
    file_path = workspace.root / "result.csv"
    file_path.write_text("a,b\n1,2\n", encoding="utf-8")

    catalog = FileCatalog(tmp_path / "files.json")
    catalog.reconcile_workspace(workspace)
    first = catalog.get_by_path("ws", "result.csv")

    assert first is not None
    assert first["file_id"].startswith("f_")
    assert first["path"] == "result.csv"

    file_path.write_text("a,b\n1,3\n", encoding="utf-8")
    catalog.reconcile_workspace(workspace)
    second = catalog.get_by_path("ws", "result.csv")

    assert second["file_id"] == first["file_id"]
    assert second["version"] == first["version"] + 1


def test_catalog_marks_deleted_files(tmp_path: Path):
    workspace = Workspace(id="ws", name="Workspace", root=tmp_path / "workspace")
    workspace.root.mkdir()
    file_path = workspace.root / "result.csv"
    file_path.write_text("data", encoding="utf-8")

    catalog = FileCatalog(tmp_path / "files.json")
    catalog.reconcile_workspace(workspace)
    file_id = catalog.get_by_path("ws", "result.csv")["file_id"]

    file_path.unlink()
    catalog.reconcile_workspace(workspace)

    deleted = catalog.get(file_id)
    assert deleted["deleted_at"] is not None
    assert catalog.list_workspace("ws") == []
