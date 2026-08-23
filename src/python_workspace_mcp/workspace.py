from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import Settings


@dataclass(frozen=True)
class Workspace:
    id: str
    name: str
    root: Path

    def resolve(self, relative_path: str) -> Path:
        candidate = (self.root / relative_path).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("Path escapes the workspace") from exc
        return candidate

    def storage_used_bytes(self) -> int:
        total = 0
        if not self.root.exists():
            return total
        for path in self.root.rglob("*"):
            if path.is_file():
                total += path.stat().st_size
        return total

    def info(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "status": "ready",
            "storage": {"used_bytes": self.storage_used_bytes()},
        }


def create_workspace(settings: Settings) -> Workspace:
    settings.workspace_path.mkdir(parents=True, exist_ok=True)
    return Workspace(
        id=settings.workspace_id,
        name=settings.workspace_name,
        root=settings.workspace_path,
    )
