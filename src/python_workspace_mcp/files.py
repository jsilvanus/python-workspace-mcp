from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import mimetypes
import uuid

from .workspace import Workspace


@dataclass(frozen=True)
class FileRecord:
    id: str
    workspace_id: str
    relative_path: str
    name: str
    size_bytes: int
    mime_type: str

    def as_dict(self) -> dict:
        return {
            "file_id": self.id,
            "workspace_id": self.workspace_id,
            "path": self.relative_path,
            "name": self.name,
            "size_bytes": self.size_bytes,
            "mime_type": self.mime_type,
        }


class FileManager:
    """Resolve workspace files through opaque IDs and safe relative paths."""

    def __init__(self, workspace: Workspace):
        self.workspace = workspace
        self.root = workspace.root.resolve()

    def _safe_path(self, relative_path: str) -> Path:
        candidate = (self.root / relative_path).resolve()
        if candidate != self.root and self.root not in candidate.parents:
            raise ValueError("File path escapes workspace")
        return candidate

    def _id_for(self, relative_path: str) -> str:
        return "file_" + hashlib.sha256(f"{self.workspace.id}:{relative_path}".encode()).hexdigest()[:24]

    def _record(self, path: Path) -> FileRecord:
        relative = path.relative_to(self.root).as_posix()
        return FileRecord(
            id=self._id_for(relative), workspace_id=self.workspace.id,
            relative_path=relative, name=path.name, size_bytes=path.stat().st_size,
            mime_type=mimetypes.guess_type(path.name)[0] or "application/octet-stream",
        )

    def list(self) -> list[FileRecord]:
        if not self.root.exists():
            return []
        return [self._record(p) for p in sorted(self.root.rglob("*")) if p.is_file()]

    def resolve_id(self, file_id: str) -> tuple[FileRecord, Path]:
        for record in self.list():
            if record.id == file_id:
                return record, self._safe_path(record.relative_path)
        raise ValueError(f"Unknown file: {file_id}")

    def read_text(self, file_id: str, max_bytes: int = 2 * 1024 * 1024) -> str:
        record, path = self.resolve_id(file_id)
        if record.mime_type.startswith("text/") or path.suffix.lower() in {".py", ".json", ".csv", ".md", ".txt", ".yaml", ".yml"}:
            return path.read_text(encoding="utf-8")[:max_bytes]
        raise ValueError("File is not a supported text file")

    def delete(self, file_id: str) -> None:
        _, path = self.resolve_id(file_id)
        path.unlink()
