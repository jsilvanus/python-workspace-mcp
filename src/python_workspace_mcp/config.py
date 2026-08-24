from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    host: str = "0.0.0.0"
    port: int = 8000
    api_key: str | None = None
    workspace_id: str = "default"
    workspace_name: str = "Default Workspace"
    workspace_path: Path = Path("./workspace")
    docker_image: str = "python-workspace-mcp-runtime:0.1"
    docker_container: str = "python-workspace-mcp-runtime"
    public_base_url: str = "http://localhost:8000"
    execution_timeout: int = 60

    @classmethod
    def from_env(cls) -> "Settings":
        path = Path(os.getenv("PYTHON_WORKSPACE_PATH", "./workspace")).expanduser().resolve()
        return cls(
            host=os.getenv("PYTHON_WORKSPACE_HOST", "0.0.0.0"),
            port=int(os.getenv("PYTHON_WORKSPACE_PORT", "8000")),
            api_key=os.getenv("PYTHON_WORKSPACE_API_KEY"),
            workspace_id=os.getenv("PYTHON_WORKSPACE_ID", "default"),
            workspace_name=os.getenv("PYTHON_WORKSPACE_NAME", "Default Workspace"),
            workspace_path=path,
            docker_image=os.getenv("PYTHON_WORKSPACE_DOCKER_IMAGE", "python-workspace-mcp-runtime:0.1"),
            docker_container=os.getenv("PYTHON_WORKSPACE_DOCKER_CONTAINER", "python-workspace-mcp-runtime"),
            public_base_url=os.getenv("PYTHON_WORKSPACE_PUBLIC_URL", "http://localhost:8000").rstrip("/"),
            execution_timeout=int(os.getenv("PYTHON_WORKSPACE_EXECUTION_TIMEOUT", "60")),
        )
