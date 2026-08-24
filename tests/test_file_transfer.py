from pathlib import Path

from python_workspace_mcp.workspace import Workspace


def test_workspace_resolves_uploaded_nested_file(tmp_path: Path):
    workspace = Workspace(id="test", name="Test", root=tmp_path)
    target = workspace.resolve("input/data.csv")
    target.parent.mkdir(parents=True)
    target.write_bytes(b"a,b\n1,2\n")
    assert target.read_bytes().startswith(b"a,b")


def test_workspace_rejects_escape(tmp_path: Path):
    workspace = Workspace(id="test", name="Test", root=tmp_path)
    try:
        workspace.resolve("../outside.txt")
    except ValueError:
        return
    raise AssertionError("workspace path escaped root")
