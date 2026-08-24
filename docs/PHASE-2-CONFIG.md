# Phase 2 configuration example

The server can expose multiple workspaces from environment configuration.

```bash
export PYTHON_WORKSPACE_WORKSPACES='stats:Statistics:/srv/workspaces/stats,sim:Simulation:/srv/workspaces/sim'
export PYTHON_WORKSPACE_ID='stats'
export PYTHON_WORKSPACE_CPU_LIMIT='2'
export PYTHON_WORKSPACE_MEMORY_LIMIT_BYTES='4294967296'
export PYTHON_WORKSPACE_STORAGE_LIMIT_BYTES='10737418240'
export PYTHON_WORKSPACE_PIDS_LIMIT='128'
export PYTHON_WORKSPACE_EXECUTION_TIMEOUT='60'
export PYTHON_WORKSPACE_MAX_OUTPUT_BYTES='2097152'
export PYTHON_WORKSPACE_MAX_ARTIFACTS='50'
```

For a second workspace, the runtime creates a separate container named from the workspace ID, for example:

```text
python-workspace-mcp-stats
python-workspace-mcp-sim
```

Workspace IDs must match:

```text
[A-Za-z0-9][A-Za-z0-9_-]{0,63}
```

The server process needs access to every configured workspace directory because it performs artifact discovery and HTTP file serving. The Docker daemon must also be able to mount those same paths.

## Important deployment note

If the MCP server itself is put inside a container while it controls the host Docker daemon through `/var/run/docker.sock`, host-path mapping must be designed explicitly. Phase 2 does not silently assume that a path visible inside the MCP server container is also visible at the same path to the Docker daemon. A production deployment should either run the MCP control plane with appropriate host path visibility or introduce a dedicated execution service.
