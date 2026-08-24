from __future__ import annotations

import base64
import hashlib
import hmac
from pathlib import Path

import uvicorn
from mcp.server.fastmcp import FastMCP
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, Response
from starlette.routing import Route

from . import __version__
from .config import Settings
from .execution import DockerExecutionBackend, ResourceLimitError
from .users import UserManager
from .workspaces import WorkspaceManager


settings = Settings.from_env()
users = UserManager.from_settings(settings) if hasattr(UserManager, "from_settings") else UserManager(
    __import__("python_workspace_mcp.users", fromlist=["User"]).User(settings.user_id, settings.user_name)
)
workspaces = WorkspaceManager(settings)
executors: dict[str, DockerExecutionBackend] = {}

mcp = FastMCP(
    "Python Workspace MCP",
    stateless_http=True,
    json_response=True,
)


def _workspace(workspace_id: str | None):
    definition = workspaces.get_definition(workspace_id)
    _authorize_workspace(definition.owner_user_id)
    return workspaces.get(definition.id)


def _authorize_workspace(owner_user_id: str) -> None:
    if owner_user_id != users.current().id:
        raise ValueError("Workspace is not owned by the current user")


def _executor(workspace_id: str | None) -> DockerExecutionBackend:
    definition = workspaces.get_definition(workspace_id)
    _authorize_workspace(definition.owner_user_id)
    workspace = workspaces.get(definition.id)
    if definition.id not in executors:
        container_name = f"{settings.docker_container_prefix}-{definition.id}"
        executors[definition.id] = DockerExecutionBackend(
            image=settings.docker_image,
            container_name=container_name,
            workspace=workspace,
            limits=definition.limits,
        )
    return executors[definition.id]


@mcp.tool()
def get_user() -> dict:
    """Return the authenticated user's stable identity."""
    return users.info()


@mcp.tool()
def get_workspaces() -> dict:
    """List workspaces available to the current user."""
    return {
        "user_id": users.current().id,
        "workspaces": [
            info for info in workspaces.all_info()
            if info["owner_user_id"] == users.current().id
        ],
        "default_workspace_id": settings.default_workspace_id,
    }


@mcp.tool()
def get_workspace(workspace_id: str | None = None) -> dict:
    """Return information about a workspace."""
    _workspace(workspace_id)
    return workspaces.info(workspace_id)


@mcp.tool()
def get_system_info() -> dict:
    """Return server, API, deployment-profile, runtime and capability information."""
    default = workspaces.get_definition()
    _authorize_workspace(default.owner_user_id)
    return {
        "server_version": __version__,
        "api_version": "1",
        "deployment_profile": "sandboxed",
        "transport": "streamable-http",
        "user": users.info(),
        "runtime": {
            "execution_backend": "docker",
            "docker_image": settings.docker_image,
        },
        "workspace": {
            "count": len(workspaces.ids()),
            "default_workspace_id": settings.default_workspace_id,
        },
        "capabilities": {
            "persistent_workspace": True,
            "multiple_workspaces": len(workspaces.ids()) > 1,
            "docker_execution": True,
            "artifacts": True,
            "resource_limits": True,
            "network_access": False,
            "non_root_runtime": True,
            "read_only_runtime_filesystem": True,
            "multiple_users": False,
        },
        "limits": default.limits.as_dict(),
    }


@mcp.tool()
def execute_python(code: str, workspace_id: str | None = None) -> dict:
    """Execute Python in a workspace and return structured results and generated artifacts."""
    try:
        return _executor(workspace_id).execute(code)
    except ResourceLimitError as exc:
        return {"success": False, "error": str(exc), "resource_limit": True}


@mcp.tool()
def list_files(workspace_id: str | None = None, path: str = ".") -> dict:
    """List files and directories in a workspace path."""
    workspace = _workspace(workspace_id)
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
    """Read a UTF-8 text file from a workspace."""
    workspace = _workspace(workspace_id)
    target = workspace.resolve(path)
    if not target.is_file():
        raise ValueError(f"Not a file: {path}")
    return {"workspace_id": workspace.id, "path": path, "content": target.read_text(encoding="utf-8")}


@mcp.tool()
def delete_file(path: str, workspace_id: str | None = None) -> dict:
    """Delete a file from a workspace."""
    workspace = _workspace(workspace_id)
    target = workspace.resolve(path)
    if not target.is_file():
        raise ValueError(f"Not a file: {path}")
    target.unlink()
    return {"workspace_id": workspace.id, "deleted": True, "path": path}


@mcp.tool()
def get_file_url(path: str, workspace_id: str | None = None) -> dict:
    """Return an authorized URL for a workspace artifact."""
    workspace = _workspace(workspace_id)
    target = workspace.resolve(path)
    if not target.is_file():
        raise ValueError(f"Not a file: {path}")
    token = _file_token(workspace.id, path)
    return {
        "workspace_id": workspace.id,
        "path": path,
        "url": f"{settings.public_base_url}/files/{workspace.id}/{_encode_path(path)}?token={token}",
    }


def _encode_path(path: str) -> str:
    return "/".join(base64.urlsafe_b64encode(part.encode()).decode().rstrip("=") for part in Path(path).parts)


def _decode_path(encoded: str) -> str:
    parts = []
    for part in encoded.split("/"):
        padding = "=" * (-len(part) % 4)
        parts.append(base64.urlsafe_b64decode(part + padding).decode())
    return "/".join(parts)


def _file_token(workspace_id: str, path: str) -> str:
    secret = (settings.api_key or "phase-2-local-secret").encode()
    payload = f"{workspace_id}\0{path}".encode()
    return hmac.new(secret, payload, hashlib.sha256).hexdigest()


async def healthz(request: Request) -> Response:
    return JSONResponse({"status": "ok", "version": __version__, "workspaces": len(workspaces.ids())})


async def file_download(request: Request) -> Response:
    workspace_id = request.path_params["workspace_id"]
    encoded = request.path_params["path"]
    try:
        definition = workspaces.get_definition(workspace_id)
        _authorize_workspace(definition.owner_user_id)
        workspace = workspaces.get(workspace_id)
        path = _decode_path(encoded)
        expected = _file_token(workspace.id, path)
        supplied = request.query_params.get("token", "")
        if not hmac.compare_digest(supplied, expected):
            return JSONResponse({"error": "invalid token"}, status_code=403)
        target = workspace.resolve(path)
    except (ValueError, UnicodeError):
        return JSONResponse({"error": "invalid path"}, status_code=400)
    if not target.is_file():
        return JSONResponse({"error": "file not found"}, status_code=404)
    return FileResponse(target)


class ApiKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/healthz" or request.url.path.startswith("/files/"):
            return await call_next(request)
        if settings.api_key:
            supplied = request.headers.get("authorization", "")
            if not hmac.compare_digest(supplied, f"Bearer {settings.api_key}"):
                return JSONResponse(
                    {"error": "unauthorized"},
                    status_code=401,
                    headers={"WWW-Authenticate": "Bearer"},
                )
        return await call_next(request)


app = mcp.streamable_http_app(
    custom_starlette_routes=[
        Route("/healthz", healthz, methods=["GET"]),
        Route("/files/{workspace_id}/{path:path}", file_download, methods=["GET"]),
    ]
)
app.add_middleware(ApiKeyMiddleware)


def main() -> None:
    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
