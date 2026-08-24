# ADR 0004 — Phase 2 Docker isolation and resource limits

## Status

Accepted / implementing.

## Context

Phase 1 provides one Docker-backed Python workspace. The next requirement is to support multiple persistent workspaces while preventing one workspace's computation from freely affecting another or the host.

The MCP API already accepts an optional workspace ID, so the external API does not need a new version merely because the server becomes multi-workspace.

## Decision

Phase 2 uses one Docker runtime container per workspace and applies container-level controls:

- non-root execution;
- network disabled by default;
- all capabilities dropped;
- `no-new-privileges`;
- read-only container filesystem;
- writable workspace mount only;
- bounded `/tmp`;
- CPU, memory and PID limits;
- execution timeout;
- application-level workspace storage quota;
- bounded execution output and artifact count.

Workspace definitions are configuration-backed in Phase 2. A later phase may move the registry into persistent application storage without changing the MCP workspace abstraction.

## Consequences

### Positive

- Workspaces have a clear execution isolation boundary.
- Containers can be recreated without losing workspace data.
- Resource controls are enforced outside Python code.
- The MCP API remains API version 1.
- The architecture leaves a path toward a dedicated execution service/scheduler.

### Negative / limitations

- Docker is still a host-level security dependency.
- Application-level storage quotas are not equivalent to hard filesystem quotas.
- Multiple containers increase operational complexity.
- A production deployment needs careful host-path and Docker-daemon configuration.

## Validation

The implementation must be tested with a real Docker runtime before Phase 2 is considered complete. In particular, verify network isolation, non-root permissions, read-only filesystem behavior, CPU/memory/PID enforcement, persistence, and cross-workspace isolation.
