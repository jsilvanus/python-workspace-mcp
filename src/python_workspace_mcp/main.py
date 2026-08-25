from __future__ import annotations

import base64
import hashlib
import hmac
from contextvars import ContextVar
from pathlib import Path

import uvicorn
from mcp.server import MCPServer
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, Response

from . import __version__
from .execution import DockerExecutionBackend, ResourceLimitError
from .limits import ResourceLimits
from .users import Principal, UserManager
from .workspaces import WorkspaceManager

settings = Settings.from_env()
users = UserManager.from_settings(settings)
workspaces = WorkspaceManager(settings)
executors: dict[str, DockerExecutionBackend] = {}
_current_principal: ContextVar[Principal | None] = ContextVar("current_principal", default=None)
mcp = MCPServer("Python Workspace MCP", version=__version__)


def _principal() -> Principal:
    principal = _current_principal.get()
    if principal is None:
        return users.principal()
    return principal


def _current_user_id() -> str:
    return _principal().user.id


def _workspace(workspace_id: str | None):
    definition = workspaces.get_definition(workspace_id)
    if definition.owner_user_id != _current_user_id():
        raise ValueError("Workspace is not owned by the current user")
    return workspaces.get(definition.id)


def _executor(workspace_id: str | None) -> DockerExecutionBackend:
    definition = workspaces.get_definition(workspace_id)
    if definition.owner_user_id != _current_user_id():
        raise ValueError("Workspace is not owned by the current user")
    workspace = workspaces.get(definition.id)
    executor = executors.get(definition.id)
    if executor is None:
        executor = DockerExecutionBackend(image=settings.docker_image, container_name=f"{settings.docker_container_prefix}-{definition.id}", workspace=workspace, limits=definition.limits)
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
    if definition.owner_user_id != _current_user_id():
        raise ValueError("Workspace is not owned by the current user")
    defaults = definition.limits
    values = {"cpu": defaults.cpu, "memory_bytes": defaults.memory_bytes, "storage_bytes": defaults.storage_bytes, "execution_timeout_seconds": defaults.execution_timeout_seconds, "pids": defaults.pids, "max_output_bytes": defaults.max_output_bytes, "max_artifacts_per_execution": defaults.max_artifacts_per_execution}
    aliases = {"timeout": "execution_timeout_seconds", "output_bytes": "max_output_bytes", "max_artifacts": "max_artifacts_per_execution"}
    for key, value in resources.items():
        key = aliases.get(key, key)
        if key == "storage_bytes":
            raise ValueError("storage_bytes is a workspace policy and cannot be changed per execution")
        if key not in values or not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValueError(f"Invalid resource: {key}")
        values[key] = value
    return workspaces.profiles.get(definition.profile_id).validate(ResourceLimits(**values))


@mcp.tool()
def get_user() -> dict:
    """Return the authenticated user's stable identity."""
    return users.info(_current_user_id())


@mcp.tool()
def get_workspaces() -> dict:
    """List workspaces available to the authenticated user."""
    user_id = _current_user_id()
    return {"user_id": user_id, "workspaces": [w for w in workspaces.all_info() if w["owner_user_id"] == user_id], "default_workspace_id": settings.default_workspace_id}


@mcp.tool()
def get_workspace(workspace_id: str | None = None) -> dict:
    """Return information about a workspace owned by the current user."""
    _workspace(workspace_id)
    return workspaces.info(workspace_id)


@mcp.resource("workspace://{workspace_id}/info")
def workspace_info_resource(workspace_id: str) -> str:
    """Current workspace metadata and execution capabilities."""
    info = workspaces.info(workspace_id)
    if info["owner_user_id"] != _current_user_id():
        raise ValueError("Workspace is not owned by the current user")
    import json
    return json.dumps({"workspace_id": info["id"], "name": info["name"], "resource_profile": info["resource_profile"], "limits": info["limits"], "maximum_limits": info["maximum_limits"], "runtime": {"backend": "docker"}, "capabilities": {"package_install": False, "outbound_network": False, "file_upload": True, "file_download": True}}, indent=2)


@mcp.tool()
def get_system_info() -> dict:
    """Return server, API, deployment-profile, runtime and capability information."""
    visible = [w for w in workspaces.all_info() if w["owner_user_id"] == _current_user_id()]
    default = workspaces.get_definition()
    return {"server_version": __version__, "api_version": "1", "mcp_sdk_major": 2, "deployment_profile": "self-hosted", "transport": "streamable-http", "user": users.info(_current_user_id()), "runtime": {"execution_backend": "docker", "docker_image": settings.docker_image}, "workspace": {"count": len(visible), "default_workspace_id": settings.default_workspace_id}, "capabilities": {"persistent_workspace": True, "multiple_workspaces": len(visible) > 1, "docker_execution": True, "artifacts": True, "resource_limits": True, "resource_profiles": True, "on_demand_resources": True, "network_access": False, "non_root_runtime": True, "read_only_runtime_filesystem": True, "multiple_users": True}, "limits": default.limits.as_dict(), "maximum_limits": default.maximum_limits.as_dict(), "resource_profile": default.profile_id}


def _execution_response(result: dict, workspace_id: str | None, resources: dict | None) -> dict:
    result["resource_profile"] = workspaces.get_definition(workspace_id).profile_id
    result["requested_resources"] = resources
    return result


@mcp.tool()
def execute_python(code: str, workspace_id: str | None = None, resources: dict | None = None) -> dict:
    """Execute ephemeral Python code in the workspace sandbox. Code is not saved as a workspace file."""
    try:
        limits = _requested_limits(workspace_id, resources)
        return _execution_response(_executor(workspace_id).execute(code, limits), workspace_id, resources)
    except ResourceLimitError as exc:
        return {"success": False, "error": str(exc), "resource_limit": True}


@mcp.tool()
def execute_file(path: str, workspace_id: str | None = None, resources: dict | None = None) -> dict:
    """Execute a persistent .py file from the workspace. No process arguments are accepted."""
    try:
        limits = _requested_limits(workspace_id, resources)
        return _execution_response(_executor(workspace_id).execute_file(path, limits), workspace_id, resources)
    except ResourceLimitError as exc:
        return {"success": False, "error": str(exc), "resource_limit": True}


@mcp.tool()
def list_files(workspace_id: str | None = None, path: str = ".") -> dict:
    """List files and directories in a workspace path."""
    workspace = _workspace(workspace_id)
    root = workspace.resolve(path)
    if not root.exists() or not root.is_dir():
        raise ValueError(f"Not a directory: {path}")
    entries = [{"name": item.name, "path": item.relative_to(workspace.root).as_posix(), "type": "directory" if item.is_dir() else "file", "size_bytes": item.stat().st_size if item.is_file() else None} for item in sorted(root.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))]
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


def _encode_path(path: str) -> str:
    return "/".join(base64.urlsafe_b64encode(part.encode()).decode().rstrip("=") for part in Path(path).parts)


def _decode_path(encoded: str) -> str:
    return "/".join(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)).decode() for part in encoded.split("/"))


def _file_token(workspace_id: str, path: str) -> str:
    return hmac.new(settings.file_signing_secret.encode(), f"{workspace_id}\0{path}".encode(), hashlib.sha256).hexdigest()


@mcp.tool()
def get_file_url(path: str, workspace_id: str | None = None) -> dict:
    """Return an authorized URL for a workspace artifact."""
    workspace = _workspace(workspace_id)
    target = workspace.resolve(path)
    if not target.is_file():
        raise ValueError(f"Not a file: {path}")
    return {"workspace_id": workspace.id, "path": path, "url": f"{settings.public_base_url}/files/{workspace.id}/{_encode_path(path)}?token={_file_token(workspace.id, path)}"}


@mcp.custom_route("/healthz", methods=["GET"])
async def healthz(request: Request) -> Response:
    return JSONResponse({"status": "ok", "version": __version__, "workspaces": len(workspaces.ids())})


@mcp.custom_route("/files/{workspace_id}/{path:path}", methods=["GET"])
async def file_download(request: Request) -> Response:
    workspace_id = request.path_params["workspace_id"]
    try:
        workspace = workspaces.get(workspace_id)
        path = _decode_path(request.path_params["path"])
        if not hmac.compare_digest(request.query_params.get("token", ""), _file_token(workspace.id, path)):
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


app = mcp.streamable_http_app(json_response=True, stateless_http=True)
app.add_middleware(ApiKeyMiddleware)


def main() -> None:
    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
