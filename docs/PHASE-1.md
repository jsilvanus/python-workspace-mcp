# Phase 1 — Docker-backed single workspace

## Goal

Prove the complete workflow with Streamable HTTP MCP, one persistent workspace, Docker-backed Python execution, file operations and generated artifacts.

The Phase 1 MCP contract is deliberately workspace-aware even though only one workspace exists. Later deployment profiles must not require a redesign of the core MCP API.

## Stable MCP surface

- `get_workspaces`
- `get_workspace`
- `get_system_info`
- `execute_python`
- `list_files`
- `read_file`
- `delete_file`
- `get_file_url`

Workspace ID parameters are optional in Phase 1 and resolve to the single default workspace. They become meaningful when Phase 2 adds multiple workspaces.

## Runtime

The MCP server runs as a normal Python process. Python analysis runs inside a separate persistent Docker container. The workspace is persisted outside the container and mounted at `/workspace`.

The runtime includes:

- numpy
- pandas
- scipy
- statsmodels
- sympy
- matplotlib
- openpyxl
- seaborn

The container is disposable; workspace data is persistent.

## Execution result

`execute_python` returns structured information:

- success
- exit code
- stdout
- stderr
- duration
- timeout status
- files created/changed by the execution

Artifacts expose path, size and MIME type. `get_file_url` produces an opaque signed URL for downloading an artifact.

## Authentication

The HTTP MCP endpoint can be protected with a bearer API key using `PYTHON_WORKSPACE_API_KEY`. The health endpoint remains unauthenticated. Artifact URLs use their own opaque HMAC token so they can be opened without copying the MCP bearer header.

## Phase 1 security boundary

This is **not** the final hostile-code sandbox. The runtime is non-root and separated into a Docker container, but Phase 1 does not enforce CPU, memory, disk, network or process quotas. Those belong to Phase 2.

An execution timeout is enforced inside the runtime container to prevent a simple infinite loop from continuing indefinitely.

## Acceptance test

A Phase 1 installation is complete when an MCP client can:

1. Connect through Streamable HTTP.
2. Discover the workspace and system information.
3. Execute arbitrary analysis Python in Docker.
4. Read and write files in the persistent workspace.
5. Generate an image or other artifact.
6. Retrieve the artifact through a URL.
7. Stop/recreate the runtime container.
8. Execute another call and verify that workspace files remain.

## Deliberately deferred

- multiple workspaces
- per-workspace resource limits
- network isolation
- CPU/RAM/disk quotas
- multiple users
- web UI
- billing/SaaS
- distributed execution
