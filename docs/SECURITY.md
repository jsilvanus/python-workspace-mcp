# Security

## Phase 1 status

Phase 1 is **not a hardened hostile-code sandbox**. It uses a Docker runtime and a non-root container user, but does not yet impose the complete resource and network restrictions required for untrusted workloads.

Do not expose a Phase 1 deployment to untrusted users merely because it runs Python in Docker.

## Phase 1 controls

- Python executes outside the MCP server process.
- Runtime container runs as a non-root user.
- Only the configured workspace is mounted.
- MCP file operations enforce workspace path containment.
- Artifact downloads require a signed token.
- Optional Bearer API-key authentication protects the MCP endpoint.
- Execution has a configurable timeout inside the container.

## Phase 2 requirements

- CPU limits.
- Memory limits.
- Storage quotas.
- PID/process limits.
- Maximum output/artifact sizes.
- Network disabled by default.
- Stronger filesystem isolation.
- Cross-workspace authorization tests.
- Security regression tests.

Docker is one layer, not the complete security model.
