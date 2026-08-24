# Phase 2 — Multi-workspace isolation and resource limits

## Goal

Turn the Phase 1 single-workspace runtime into a multi-workspace execution service while keeping the MCP API at version 1.

Each workspace gets its own persistent directory and Docker container. The container is disposable; the workspace is durable.

## Architecture

```text
MCP client
   |
   | Streamable HTTP
   v
MCP server
   |
   v
WorkspaceManager
   |
   +-- workspace A --> Docker container A --> persistent data A
   |
   +-- workspace B --> Docker container B --> persistent data B
   |
   +-- workspace C --> Docker container C --> persistent data C
```

The execution boundary is still `ExecutionBackend`, so future schedulers can replace direct Docker invocation.

## Workspace configuration

Phase 2 uses configuration-backed workspaces. The environment variable is a comma-separated list of:

```text
id:name:path
```

Example:

```text
PYTHON_WORKSPACE_WORKSPACES=statistics:Statistics:/srv/workspaces/statistics,simulation:Simulation:/srv/workspaces/simulation
```

If it is omitted, the server creates the existing `default` workspace from `PYTHON_WORKSPACE_PATH`.

Workspace IDs are deliberately stable and restricted to letters, numbers, `_` and `-`.

## Container isolation

Every workspace gets a separate runtime container. Containers are configured with:

- non-root user `1000:1000`;
- no network (`--network none`);
- all Linux capabilities dropped;
- `no-new-privileges`;
- read-only container root filesystem;
- writable workspace mount only;
- a bounded `/tmp` tmpfs;
- CPU limit;
- memory limit;
- PID limit.

The container does not receive the Docker socket.

## Resource limits

Default limits are intentionally conservative and configurable:

| Resource | Default |
|---|---:|
| CPU | 2 cores |
| Memory | 4 GiB |
| Workspace storage | 10 GiB |
| Execution timeout | 60 s |
| PIDs | 128 |
| Combined stdout/stderr | 2 MiB |
| Artifacts per execution | 50 |

Storage is currently enforced as an application-level workspace quota. A future deployment backend can provide a hard filesystem quota where the storage driver supports it.

## Execution lifecycle

1. Resolve the requested workspace.
2. Check its current storage usage.
3. Ensure its container exists and is running.
4. Execute Python with the configured timeout.
5. Capture stdout/stderr.
6. Detect changed files.
7. Apply artifact-count/output limits.
8. Report execution/resource metadata.

## Stable MCP API

No new required tool is introduced for Phase 2. Existing API version 1 tools gain real multi-workspace behavior:

- `get_workspaces()` returns all visible workspaces.
- `get_workspace(workspace_id?)` resolves a specific workspace.
- `execute_python(code, workspace_id?)` executes in that workspace.
- file/artifact tools operate on the selected workspace.
- `get_system_info()` reports that resource controls are enabled.

This is the reason workspace IDs were included in the Phase 1 contract.

## Security boundary

Phase 2 is substantially safer than Phase 1, but it should not be described as a perfect security sandbox. Docker isolation depends on the host kernel and container runtime. The project should document supported runtime assumptions and continue security testing before exposing arbitrary untrusted code to the public internet.

## Remaining validation

This implementation still requires a real Docker environment to validate:

- image build;
- multiple container creation;
- actual CPU/memory/PID enforcement;
- network isolation;
- read-only root filesystem behavior;
- permissions for the non-root runtime user;
- persistence after container recreation;
- storage/output limit behavior;
- cross-workspace artifact isolation.

These are runtime validation tasks, not reasons to expand the MCP API.
