from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from threading import RLock
from typing import Any


class StateStore:
    """Small persistent JSON state store for the self-hosted deployment.

    This is intentionally simple for Phase 3. A future SaaS deployment can
    replace this implementation without changing the user/workspace domain
    model or MCP API.
    """

    def __init__(self, path: Path) -> None:
        self.path = path.expanduser().resolve()
        self._lock = RLock()

    def load(self) -> dict[str, Any]:
        with self._lock:
            if not self.path.exists():
                return {"users": {}, "api_keys": {}, "workspaces": {}, "resource_profiles": {}}
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid state file: {self.path}") from exc
            if not isinstance(data, dict):
                raise ValueError("State file root must be an object")
            return {
                "users": dict(data.get("users", {})),
                "api_keys": dict(data.get("api_keys", {})),
                "workspaces": dict(data.get("workspaces", {})),
                "resource_profiles": dict(data.get("resource_profiles", {})),
            }

    def save(self, data: dict[str, Any]) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, temporary = tempfile.mkstemp(prefix=".state-", dir=self.path.parent)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    json.dump(data, handle, indent=2, sort_keys=True)
                    handle.write("\n")
                os.replace(temporary, self.path)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
