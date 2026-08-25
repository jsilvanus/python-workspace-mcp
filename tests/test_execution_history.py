from pathlib import Path

from python_workspace_mcp.execution_history import ExecutionHistory


def test_history_is_capped_per_workspace(tmp_path: Path):
    history = ExecutionHistory(tmp_path / "executions.json", per_workspace_limit=3)
    for number in range(5):
        history.record(
            {
                "execution_id": f"exec-{number}",
                "workspace_id": "ws",
                "started_at": number,
                "finished_at": number,
                "duration_seconds": 1,
                "success": True,
                "exit_code": 0,
                "timed_out": False,
                "resource_limits": {},
                "storage_used_bytes": 0,
                "files": {"created": [], "modified": [], "deleted": []},
            },
            user_id="user",
            execution_type="execute_python",
        )

    records = history.list_workspace("ws")
    assert [record["execution_id"] for record in records] == ["exec-4", "exec-3", "exec-2"]


def test_history_retention_is_per_workspace(tmp_path: Path):
    history = ExecutionHistory(tmp_path / "executions.json", per_workspace_limit=2)
    for workspace_id in ("one", "two"):
        for number in range(3):
            history.record(
                {"execution_id": f"{workspace_id}-{number}", "workspace_id": workspace_id, "started_at": number, "finished_at": number},
                user_id="user",
                execution_type="execute_python",
            )

    assert len(history.list_workspace("one")) == 2
    assert len(history.list_workspace("two")) == 2
