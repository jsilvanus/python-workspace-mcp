from pathlib import Path

from python_workspace_mcp.execution import DockerExecutionBackend
from python_workspace_mcp.workspace import Workspace


def test_snapshot_detects_new_and_modified_files(tmp_path: Path):
    workspace = Workspace("default", "Default", tmp_path)
    backend = DockerExecutionBackend.__new__(DockerExecutionBackend)
    backend.workspace = workspace

    file_path = tmp_path / "result.txt"
    file_path.write_text("one", encoding="utf-8")
    before = backend._snapshot_files()

    file_path.write_text("two", encoding="utf-8")
    new_file = tmp_path / "plot.png"
    new_file.write_bytes(b"png")
    after = backend._snapshot_files()

    changed = sorted(
        path for path, metadata in after.items()
        if path not in before or before[path] != metadata
    )
    assert changed == ["plot.png", "result.txt"]


def test_artifact_metadata(tmp_path: Path):
    workspace = Workspace("default", "Default", tmp_path)
    backend = DockerExecutionBackend.__new__(DockerExecutionBackend)
    backend.workspace = workspace

    image = tmp_path / "plot.png"
    image.write_bytes(b"png")

    artifact = backend._artifact("plot.png")
    assert artifact["path"] == "plot.png"
    assert artifact["size_bytes"] == 3
    assert artifact["mime_type"] == "image/png"
