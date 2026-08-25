from __future__ import annotations

import mimetypes
import time
import uuid
from pathlib import Path
from threading import RLock

from .json_store import JsonStore
from .workspace import Workspace


class FileCatalog:
    """Persistent stable identities and metadata for workspace files."""

    def __init__(self, path: Path) -> None:
        self.store = JsonStore(path, lambda: {"files": {}, "path_index": {}})
        self._lock = RLock()

    def reconcile_workspace(self, workspace: Workspace) -> None:
        """Reconcile all files in a workspace, assigning stable IDs as needed."""
        with self._lock:
            state = self.store.load()
            files = state.setdefault("files", {})
            index = state.setdefault("path_index", {})
            workspace_index = index.setdefault(workspace.id, {})
            current: dict[str, Path] = {}
            if workspace.root.exists():
                for path in workspace.root.rglob("*"):
                    if path.is_file():
                        current[path.relative_to(workspace.root).as_posix()] = path
            now = time.time()
            for path_str, path in current.items():
                file_id = workspace_index.get(path_str)
                stat = path.stat()
                if file_id and file_id in files:
                    record = files[file_id]
                    changed = record.get("size_bytes") != stat.st_size or record.get("modified_at") != stat.st_mtime
                    record.update({"size_bytes": stat.st_size, "modified_at": stat.st_mtime, "mime_type": _mime_type(path), "deleted_at": None})
                    if changed:
                        record["version"] = int(record.get("version", 1)) + 1
                else:
                    file_id = f"f_{uuid.uuid4().hex}"
                    files[file_id] = {
                        "file_id": file_id,
                        "workspace_id": workspace.id,
                        "path": path_str,
                        "mime_type": _mime_type(path),
                        "size_bytes": stat.st_size,
                        "created_at": now,
                        "modified_at": stat.st_mtime,
                        "version": 1,
                        "deleted_at": None,
                    }
                    workspace_index[path_str] = file_id
            for path_str, file_id in list(workspace_index.items()):
                if path_str not in current and file_id in files and files[file_id].get("deleted_at") is None:
                    files[file_id]["deleted_at"] = now
            self.store.save(state)

    def reconcile_changes(self, workspace: Workspace, created: list[str], modified: list[str], deleted: list[str]) -> dict[str, list[dict]]:
        with self._lock:
            self.reconcile_workspace(workspace)
            state = self.store.load()
            files = state["files"]
            index = state["path_index"].setdefault(workspace.id, {})
            now = time.time()
            result = {"created": [], "modified": [], "deleted": []}
            for path_str in created:
                target = workspace.root / path_str
                result["created"].append(self._upsert(state, workspace, target, path_str, now, is_new=True))
            for path_str in modified:
                target = workspace.root / path_str
                if target.is_file():
                    result["modified"].append(self._upsert(state, workspace, target, path_str, now, is_new=False))
            for path_str in deleted:
                file_id = index.get(path_str)
                if file_id and file_id in files:
                    files[file_id]["deleted_at"] = now
                    files[file_id]["modified_at"] = now
                    files[file_id]["version"] = int(files[file_id].get("version", 1)) + 1
                    result["deleted"].append(self._public(files[file_id]))
            self.store.save(state)
            return result

    def _upsert(self, state: dict, workspace: Workspace, target: Path, path_str: str, now: float, is_new: bool) -> dict:
        files = state["files"]
        index = state["path_index"].setdefault(workspace.id, {})
        file_id = index.get(path_str)
        if file_id and file_id in files:
            record = files[file_id]
            record["size_bytes"] = target.stat().st_size
            record["modified_at"] = target.stat().st_mtime
            record["mime_type"] = _mime_type(target)
            record["version"] = int(record.get("version", 1)) + (1 if not is_new else 0)
            record["deleted_at"] = None
        else:
            file_id = f"f_{uuid.uuid4().hex}"
            stat = target.stat()
            files[file_id] = record = {
                "file_id": file_id,
                "workspace_id": workspace.id,
                "path": path_str,
                "mime_type": _mime_type(target),
                "size_bytes": stat.st_size,
                "created_at": now,
                "modified_at": stat.st_mtime,
                "version": 1,
                "deleted_at": None,
            }
            index[path_str] = file_id
        return self._public(record)

    def get_by_path(self, workspace_id: str, path: str) -> dict | None:
        state = self.store.load()
        file_id = state.get("path_index", {}).get(workspace_id, {}).get(path)
        if not file_id:
            return None
        record = state.get("files", {}).get(file_id)
        return self._public(record) if record else None

    def get(self, file_id: str) -> dict:
        state = self.store.load()
        record = state.get("files", {}).get(file_id)
        if not record:
            raise ValueError(f"Unknown file: {file_id}")
        return self._public(record)

    def list_workspace(self, workspace_id: str) -> list[dict]:
        state = self.store.load()
        return [self._public(record) for record in state.get("files", {}).values() if record.get("workspace_id") == workspace_id and record.get("deleted_at") is None]

    @staticmethod
    def _public(record: dict) -> dict:
        return dict(record)


def _mime_type(path: Path) -> str:
    return mimetypes.guess_type(path.name)[0] or "application/octet-stream"
