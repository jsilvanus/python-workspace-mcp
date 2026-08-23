from __future__ import annotations

import base64
import hashlib
import hmac
import os
from pathlib import Path

import uvicorn
from mcp.server.fastmcp import FastMCP
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, Response
from starlette.routing import Route

from . import __version__
from .config import Settings
from .execution import DockerExecutionBackend
from .workspace import Workspace, create_workspace


settings = Settings.from_env()
workspace = create_workspace(settings)
executor = DockerExecutionBackend(settings, workspace)

mcp = FastMCP(
    "Python Workspace MCP",
    stateless_http=True,
    json_response=True,
)


@mcp.tool()
def get_workspaces() -> dict:
    """List workspaces available to the caller. Phase 1 exposes one workspace."""
    return {
        "workspaces": [workspace.info()],
        "default_workspace_id": workspace.id,
    }


@mcp.tool()
def get_workspace(workspace_id: str | None = None) -> dict:
    """Return information about a workspace."""
    _require_workspace(workspace_id)
    return workspace.info()


@mcp.tool()
def get_system_info() -> dict:
    """Return server, deployment-profile, runtime and capability information."""
    return {
        "server_version": __version__,
        "api_version": "1",
        "deployment_profile": "local-docker",
        "transport": "streamable-http",
        "runtime": {"language": "python", "docker_image": settings.docker_image},
        "capabilities": {
            "persistent_workspace": True,
            "multiple_workspaces": False,
            "docker_execution": True,
            "artifacts": True,
            "resource_limits": False,
            "network_access": "not_restricted_in_phase_1",
        },
        "limits": {
            "execution_timeout_seconds": settings.execution_timeout,
            "cpu": None,
            "memory_bytes": None,
            "storage_bytes": None,
        },
    }


@mcp.tool()
def execute_python(code: str, workspace_id: str | None = None) -> dict:
    """Execute arbitrary Python in the Docker-backed workspace and return results and generated artifacts."""
    _require_workspace(workspace_id)
    return executor.execute(code)


@mcp.tool()
def list_files(workspace_id: str | None = None, path: str = ".") -> dict:
    """List files and directories in a workspace path."""
    _require_workspace(workspace_id)
    root = workspace.resolve(path)
    if not root.exists():
        raise ValueError(f"Path does not exist: {path}")
    if not root.is_dir():
        raise ValueError(f"Not a directory: {path}")
    entries = []
    for item in sorted(root.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
        entries.append({
            "name": item.name,
            "path": item.relative_to(workspace.root).as_posix(),
            "type": "directory" if item.is_dir() else "file",
            "size_bytes": item.stat().st_size if item.is_file() else None,
        })
    return {"workspace_id": workspace.id, "path": path, "entries": entries}


@mcp.tool()
def read_file(path: str, workspace_id: str | None = None) -> dict:
    """Read a UTF-8 text file from the workspace."""
    _require_workspace(workspace_id)
    target = workspace.resolve(path)
    if not target.is_file():
        raise ValueError(f"Not a file: {path}")
    return {"path": path, "content": target.read_text(encoding="utf-8")}


@mcp.tool()
def delete_file(path: str, workspace_id: str | None = None) -> dict:
    """Delete a file from the workspace."""
    _require_workspace(workspace_id)
    target = workspace.resolve(path)
    if not target.is_file():
        raise ValueError(f"Not a file: {path}")
    target.unlink()
    return {"deleted": True, "path": path}


@mcp.tool()
def get_file_url(path: str, workspace_id: str | None = None) -> dict:
    """Return a URL for a workspace artifact. The URL is protected by a short opaque token."""
    _require_workspace(workspace_id)
    target = workspace.resolve(path)
    if not target.is_file():
        raise ValueError(f"Not a file: {path}")
    token = _file_token(path)
    return {"path": path, "url": f"{settings.public_base_url}/files/{_encode_path(path)}?token={token}"}


def _require_workspace(workspace_id: str | None) -> None:
    if workspace_id is not None and workspace_id != workspace.id:
        raise ValueError(f"Unknown workspace: {workspace_id}")


def _encode_path(path: str) -> str:
    return "/".join(base64.urlsafe_b64encode(part.encode()).decode().rstrip("=") for part in Path(path).parts)


def _decode_path(encoded: str) -> str:
    parts = []
    for part in encoded.split("/"):
        padding = "=" * (-len(part) % 4)
        parts.append(base64.urlsafe_b64decode(part + padding).decode())
    return "/".join(parts)


def _file_token(path: str) -> str:
    secret = (settings.api_key or "phase-1-local-secret").encode()
    return hmac.new(secret, path.encode(), hashlib.sha256).hexdigest()


async def healthz(request: Request) -> Response:
    return JSONResponse({"status": "ok", "version": __version__})


async def file_download(request: Request) -> Response:
    encoded = request.path_params["path"]
    path = _decode_path(encoded)
    expected = _file_token(path)
    supplied = request.query_params.get("token", "")
    if not hmac.compare_digest(supplied, expected):
        return JSONResponse({"error": "invalid token"}, status_code=403)
    target = workspace.resolve(path)
    if not target.is_file():
        return JSONResponse({"error": "file not found"}, status_code=404)
    return FileResponse(target)


class ApiKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/healthz":
            return await call_next(request)
        if settings.api_key:
            supplied = request.headers.get("authorization", "")
            if not hmac.compare_digest(supplied, f"Bearer {settings.api_key}"):
                return JSONResponse({"error": "unauthorized"}, status_code=401, headers={"WWW-Authenticate": "Bearer"})
        return await call_next(request)


app = mcp.streamable_http_app(
    custom_starlette_routes=[
        Route("/healthz", healthz, methods=["GET"]),
        Route("/files/{path:path}", file_download, methods=["GET"]),
    ]
)
app.add_middleware(ApiKeyMiddleware)


def main() -> None:
    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
