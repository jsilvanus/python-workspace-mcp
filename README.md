# Python Workspace MCP

A persistent Python analysis workspace exposed to AI agents through Model Context Protocol (MCP).

Phase 1 provides a single Docker-backed workspace over **Streamable HTTP**. The MCP API is intentionally workspace-aware from the beginning so later deployment profiles can add multiple workspaces without redesigning the contract.

## Phase 1 status

This is the first implementation phase and is not yet a hardened sandbox. Docker provides process/filesystem separation from the MCP server, but CPU, memory, disk, network and process limits are deferred to Phase 2.

## Quick start

Requirements:

- Python 3.11+
- Docker
- an MCP client that supports Streamable HTTP

Create an environment and install the server:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e .
```

Build the runtime:

```bash
docker build -t python-workspace-mcp-runtime:0.1 runtime/
```

Start the server:

```bash
python -m python_workspace_mcp.main
```

The MCP endpoint is:

```text
http://localhost:8000/mcp
```

For a non-local deployment, set `PYTHON_WORKSPACE_API_KEY` and connect with `Authorization: Bearer <key>`.

## MCP surface

- `get_workspaces`
- `get_workspace`
- `get_system_info`
- `execute_python`
- `list_files`
- `read_file`
- `delete_file`
- `get_file_url`

## Configuration

Environment variables include:

- `PYTHON_WORKSPACE_HOST`
- `PYTHON_WORKSPACE_PORT`
- `PYTHON_WORKSPACE_API_KEY`
- `PYTHON_WORKSPACE_PATH`
- `PYTHON_WORKSPACE_ID`
- `PYTHON_WORKSPACE_NAME`
- `PYTHON_WORKSPACE_DOCKER_IMAGE`
- `PYTHON_WORKSPACE_DOCKER_CONTAINER`
- `PYTHON_WORKSPACE_PUBLIC_URL`
- `PYTHON_WORKSPACE_EXECUTION_TIMEOUT`

See `docs/PLAN.md` and `docs/DEPLOYMENT-PROFILES.md` for the long-term architecture.
