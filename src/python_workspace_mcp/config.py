from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    host: str = "0.0.0.0"
    port: int = 8000
    api_key: str | None = None
    user_id: str = "default"
    user_name: str = "Default User"
    default_workspace_id: str = "default"
    workspace_name: str = "Default Workspace"
    workspace_path: Path = Path("./workspace")
    workspace_definitions: str = ""
    state_path: Path = Path("./data/state.json")
    require_auth: bool = False
    docker_image: str = "python-workspace-mcp-runtime:0.1"
    docker_container_prefix: str = "python-workspace-mcp"
    public_base_url: str = "http://localhost:8000"
    execution_timeout: int = 60
    cpu_limit: float = 2.0
    memory_limit_bytes: int = 4 * 1024 * 1024 * 1024
    storage_limit_bytes: int = 10 * 1024 * 1024 * 1024
    pids_limit: int = 128
    max_output_bytes: int = 2 * 1024 * 1024
    max_artifacts_per_execution: int = 50

    @classmethod
    def from_env(cls) -> "Settings":
        path = Path(os.getenv("PYTHON_WORKSPACE_PATH", "./workspace")).expanduser().resolve()
        state_path = Path(os.getenv("PYTHON_WORKSPACE_STATE", "./data/state.json")).expanduser().resolve()
        return cls(
            host=os.getenv("PYTHON_WORKSPACE_HOST", "0.0.0.0"),
            port=int(os.getenv("PYTHON_WORKSPACE_PORT", "8000")),
            api_key=os.getenv("PYTHON_WORKSPACE_API_KEY"),
            user_id=os.getenv("PYTHON_WORKSPACE_USER_ID", "default"),
            user_name=os.getenv("PYTHON_WORKSPACE_USER_NAME", "Default User"),
            default_workspace_id=os.getenv("PYTHON_WORKSPACE_ID", "default"),
            workspace_name=os.getenv("PYTHON_WORKSPACE_NAME", "Default Workspace"),
            workspace_path=path,
            workspace_definitions=os.getenv("PYTHON_WORKSPACE_WORKSPACES", ""),
            state_path=state_path,
            require_auth=os.getenv("PYTHON_WORKSPACE_REQUIRE_AUTH", "false").lower() in {"1", "true", "yes", "on"},
            docker_image=os.getenv("PYTHON_WORKSPACE_DOCKER_IMAGE", "python-workspace-mcp-runtime:0.1"),
            docker_container_prefix=os.getenv("PYTHON_WORKSPACE_DOCKER_PREFIX", "python-workspace-mcp"),
            public_base_url=os.getenv("PYTHON_WORKSPACE_PUBLIC_URL", "http://localhost:8000").rstrip("/"),
            execution_timeout=int(os.getenv("PYTHON_WORKSPACE_EXECUTION_TIMEOUT", "60")),
            cpu_limit=float(os.getenv("PYTHON_WORKSPACE_CPU_LIMIT", "2")),
            memory_limit_bytes=int(os.getenv("PYTHON_WORKSPACE_MEMORY_LIMIT_BYTES", str(4 * 1024 * 1024 * 1024))),
            storage_limit_bytes=int(os.getenv("PYTHON_WORKSPACE_STORAGE_LIMIT_BYTES", str(10 * 1024 * 1024 * 1024))),
            pids_limit=int(os.getenv("PYTHON_WORKSPACE_PIDS_LIMIT", "128")),
            max_output_bytes=int(os.getenv("PYTHON_WORKSPACE_MAX_OUTPUT_BYTES", str(2 * 1024 * 1024))),
            max_artifacts_per_execution=int(os.getenv("PYTHON_WORKSPACE_MAX_ARTIFACTS", "50")),
        )
