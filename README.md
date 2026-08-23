# Python Workspace MCP

A persistent Python analysis workspace exposed to AI agents through Model Context Protocol (MCP).

Phase 1 provides a single Docker-backed workspace over **Streamable HTTP**. The MCP API is intentionally workspace-aware from the beginning so later deployment profiles can add multiple workspaces without redesigning the contract.

## Phase 1 status

The Phase 1 code, contract, tests and documentation are being completed on the `phase-1` branch. It is **not yet a hardened sandbox** and still requires real Docker/MCP end-to-end validation before it should be considered complete.

Docker provides process/filesystem separation from the MCP server, but CPU, memory, disk, PID, network and stronger isolation controls are deferred to Phase 2.

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

Build the Python runtime:

```bash
docker build -t python-workspace-mcp-runtime:0.1 runtime/
```

Start the MCP server:

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

`get_workspaces` returns one workspace in Phase 1. Workspace IDs are already part of the contract where relevant so Phase 2 can activate multiple workspaces without changing the tool model.

## Runtime

The initial runtime includes:

- numpy
- pandas
- scipy
- statsmodels
- sympy
- matplotlib
- seaborn
- openpyxl

The package set is defined in `runtime/requirements.txt` and can evolve independently of the MCP contract.

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

See `docs/PLAN.md`, `docs/MCP-INTERFACE.md`, `docs/SECURITY.md` and `docs/DEPLOYMENT-PROFILES.md` for the architecture and roadmap.
