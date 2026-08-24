from __future__ import annotations

import base64
import hashlib
import hmac
from contextvars import ContextVar
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
from .limits import ResourceLimits
from .users import Principal, UserManager
from .workspaces import WorkspaceManager


settings = Settings.from_env()
users = UserManager.from_settings(settings)
workspaces = WorkspaceManager(settings)
executors: dict[str, DockerExecutionBackend] = {}
_current_principal: ContextVar[Principal | None] = ContextVar("current_principal", default=None)

mcp = FastMCP("Python Workspace MCP", stateless_http=True, json_response=True)


def _principal() -> Principal:
    principal = _current_principal.get()
    if principal is None:
        return users.principal()
    return principal


def _current_user_id() -> str:
    return _principal().user.id


def _workspace(workspace_id: str | None):
    definition = workspaces.get_definition(workspace_id)
    _authorize_workspace(definition.owner_user_id)
    return workspaces.get(definition.id)


def _authorize_workspace(owner_user_id: str) -> None:
    if owner_user_id != _current_user_id():
        raise ValueError("Workspace is not owned by the current user")


def _executor(workspace_id: str | None) -> DockerExecutionBackend:
    definition = workspaces.get_definition(workspace_id)
    _authorize_workspace(definition.owner_user_id)
    workspace = workspaces.get(definition.id)
    executor = executors.get(definition.id)
    if executor is None:
        executor = DockerExecutionBackend(
            image=settings.docker_image,
            container_name=f"{settings.docker_container_prefix}-{definition.id}",
            workspace=workspace,
            limits=definition.limits,
        )
        executors[definition.id] = executor
    else:
        executor.limits = definition.limits
    return executor


def _requested_limits(workspace_id: str | None, resources: dict | None) -> ResourceLimits | None:
    if resources is None:
        return None
    if not isinstance(resources, dict):
        raise ValueError("resources must be an object")
    definition = workspaces.get_definition(workspace_id)
    _authorize_workspace(definition.owner_user_id)
    allowed = definition.maximum_limits
    defaults = definition.limits
    values = {
        "cpu": defaults.cpu,
        "memory_bytes": defaults.memory_bytes,
        "storage_bytes": defaults.storage_bytes,
        "execution_timeout_seconds": defaults.execution_timeout_seconds,
        "pids": defaults.pids,
        "max_output_bytes": defaults.max_output_bytes,
        "max_artifacts_per_execution": defaults.max_artifacts_per_execution,
    }
    aliases = {"timeout": "execution_timeout_seconds", "output_bytes": "max_output_bytes", "max_artifacts": "max_artifacts_per_execution"}
    for key, value in resources.items():
        key = aliases.get(key, key)
        if key not in values:
            raise ValueError(f"Unknown resource: {key}")
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValueError(f"Resource {key} must be numeric")
        values[key] = value
    requested = ResourceLimits(**values)
    return workspaces.profiles.get(definition.profile_id).validate(requested)


@mcp.tool()
def get_user() -> dict:
    """Return the authenticated user's stable identity."""
    return users.info(_current_user_id())


@mcp.tool()
def get_workspaces() -> dict:
    """List workspaces available to the authenticated user."""
    user_id = _current_user_id()
    return {
        "user_id": user_id,
        "workspaces": [info for info in workspaces.all_info() if info["owner_user_id"] == user_id],
        "default_workspace_id": settings.default_workspace_id,
    }


@mcp.tool()
def get_workspace(workspace_id: str | None = None) -> dict:
    """Return information about a workspace owned by the current user."""
    _workspace(workspace_id)
    return workspaces.info(workspace_id)


@mcp.tool()
def get_system_info() -> dict:
    """Return server, API, deployment-profile, runtime and capability information."""
    visible = [w for w in workspaces.all_info() if w["owner_user_id"] == _current_user_id()]
    default = workspaces.get_definition()
    return {
        "server_version": __version__,
        "api_version": "1",
        "deployment_profile": "self-hosted",
        "transport": "streamable-http",
        "user": users.info(_current_user_id()),
        "runtime": {"execution_backend": "docker", "docker_image": settings.docker_image},
        "workspace": {"count": len(visible), "default_workspace_id": settings.default_workspace_id},
        "capabilities": {
            "persistent_workspace": True,
            "multiple_workspaces": len(visible) > 1,
            "docker_execution": True,
            "artifacts": True,
            "resource_limits": True,
            "resource_profiles": True,
            "on_demand_resources": True,
            "network_access": False,
            "non_root_runtime": True,
            "read_only_runtime_filesystem": True,
            "multiple_users": True,
        },
        "limits": default.limits.as_dict(),
        "maximum_limits": default.maximum_limits.as_dict(),
        "resource_profile": default.profile_id,
    }


@mcp.tool()
def execute_python(code: str, workspace_id: str | None = None, resources: dict | None = None) -> dict:
    """Execute Python, optionally requesting resources within the workspace profile maximums."""
    try:
        limits = _requested_limits(workspace_id, resources)
        result = _executor(workspace_id).execute(code, limits)
        result["resource_profile"] = workspaces.get_definition(workspace_id).profile_id
        result["requested_resources"] = resources
        return result
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
        entries.append({"name": item.name, "path": item.relative_to(workspace.root).as_posix(), "type": "directory" if item.is_dir() else "file", "size_bytes": item.stat().st_size if item.is_file() else None})
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
    return {"workspace_id": workspace.id, "path": path, "url": f"{settings.public_base_url}/files/{workspace.id}/{_encode_path(path)}?token={token}"}


def _encode_path(path: str) -> str:
    return "/".join(base64.urlsafe_b64encode(part.encode()).decode().rstrip("=") for part in Path(path).parts)


def _decode_path(encoded: str) -> str:
    parts = []
    for part in encoded.split("/"):
        padding = "=" * (-len(part) % 4)
        parts.append(base64.urlsafe_b64decode(part + padding).decode())
    return "/".join(parts)


def _file_token(workspace_id: str, path: str) -> str:
    return hmac.new(settings.file_signing_secret.encode(), f"{workspace_id}\0{path}".encode(), hashlib.sha256).hexdigest()


async def healthz(request: Request) -> Response:
    return JSONResponse({"status": "ok", "version": __version__, "workspaces": len(workspaces.ids())})


async def file_download(request: Request) -> Response:
    workspace_id = request.path_params["workspace_id"]
    encoded = request.path_params["path"]
    try:
        definition = workspaces.get_definition(workspace_id)
        workspace = workspaces.get(workspace_id)
        path = _decode_path(encoded)
        expected = _file_token(workspace.id, path)
        supplied = request.query_params.get("token", "")
        if not hmac.compare_digest(supplied, expected):
            return JSONResponse({"error": "invalid token"}, status_code=403)
        target = workspace.resolve(path)
        if definition.owner_user_id not in {u.id for u in users.all()}:
            return JSONResponse({"error": "workspace unavailable"}, status_code=404)
    except (ValueError, UnicodeError):
        return JSONResponse({"error": "invalid path"}, status_code=400)
    if not target.is_file():
        return JSONResponse({"error": "file not found"}, status_code=404)
    return FileResponse(target)


class ApiKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/healthz" or request.url.path.startswith("/files/"):
            return await call_next(request)
        supplied = request.headers.get("authorization", "")
        principal = None
        if supplied:
            if not supplied.startswith("Bearer "):
                return JSONResponse({"error": "invalid authorization"}, status_code=401, headers={"WWW-Authenticate": "Bearer"})
            raw_key = supplied[7:]
            try:
                principal = users.resolve_api_key(raw_key)
            except ValueError:
                if settings.api_key and hmac.compare_digest(raw_key, settings.api_key):
                    principal = users.principal("environment-api-key")
                else:
                    return JSONResponse({"error": "unauthorized"}, status_code=401, headers={"WWW-Authenticate": "Bearer"})
        if principal is None and settings.require_auth:
            return JSONResponse({"error": "unauthorized"}, status_code=401, headers={"WWW-Authenticate": "Bearer"})
        token = _current_principal.set(principal)
        try:
            return await call_next(request)
        finally:
            _current_principal.reset(token)


app = mcp.streamable_http_app(custom_starlette_routes=[
    Route("/healthz", healthz, methods=["GET"]),
    Route("/files/{workspace_id}/{path:path}", file_download, methods=["GET"]),
])
app.add_middleware(ApiKeyMiddleware)


def main() -> None:
    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
