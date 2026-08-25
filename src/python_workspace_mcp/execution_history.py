from __future__ import annotations

from pathlib import Path
from threading import RLock

from .json_store import JsonStore


class ExecutionHistory:
    """Bounded persistent execution history, capped per workspace."""

    def __init__(self, path: Path, per_workspace_limit: int = 100) -> None:
        if per_workspace_limit < 1:
            raise ValueError("Execution history limit must be at least 1")
        self.store = JsonStore(path, lambda: {"executions": {}})
        self.limit = per_workspace_limit
        self._lock = RLock()

    def record(self, result: dict, *, user_id: str, execution_type: str, file_id: str | None = None) -> dict:
        with self._lock:
            state = self.store.load()
            executions = state.setdefault("executions", {})
            execution_id = result["execution_id"]
            record = {
                "execution_id": execution_id,
                "user_id": user_id,
                "workspace_id": result["workspace_id"],
                "type": execution_type,
                "file_id": file_id,
                "started_at": result.get("started_at"),
                "finished_at": result.get("finished_at"),
                "duration_seconds": result.get("duration_seconds"),
                "success": result.get("success"),
                "exit_code": result.get("exit_code"),
                "timed_out": result.get("timed_out", False),
                "resource_limits": result.get("resource_limits"),
                "storage_used_bytes": result.get("storage_used_bytes"),
                "files": result.get("files", {}),
            }
            executions[execution_id] = record
            workspace_records = [item for item in executions.values() if item.get("workspace_id") == record["workspace_id"]]
            workspace_records.sort(key=lambda item: (item.get("finished_at") or 0, item.get("started_at") or 0), reverse=True)
            for stale in workspace_records[self.limit:]:
                executions.pop(stale["execution_id"], None)
            self.store.save(state)
            return record

    def list_workspace(self, workspace_id: str, limit: int | None = None) -> list[dict]:
        state = self.store.load()
        records = [item for item in state.get("executions", {}).values() if item.get("workspace_id") == workspace_id]
        records.sort(key=lambda item: (item.get("finished_at") or 0, item.get("started_at") or 0), reverse=True)
        return records[: limit or self.limit]

    def get(self, execution_id: str) -> dict:
        record = self.store.load().get("executions", {}).get(execution_id)
        if not record:
            raise ValueError(f"Unknown execution: {execution_id}")
        return record
