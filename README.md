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

Create the server's user (the server never creates one on its own — see `docs/USER-MODEL.md`):

```bash
python-workspace user add default "Default User"
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

To generate ready-to-paste client configuration (VS Code `mcp.json`, `claude mcp add`/`.mcp.json`, or a plain URL + headers block), run:

```bash
python-workspace mcp-config
```

Add `--create-key-for <user_id>` to mint a fresh API key and embed it, `--api-key <key>` to embed one you already have, `--format {vscode,claude-code,url}` to print just one format, and `--base-url` if the server is reachable at a different address than `PYTHON_WORKSPACE_PUBLIC_URL`.

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
