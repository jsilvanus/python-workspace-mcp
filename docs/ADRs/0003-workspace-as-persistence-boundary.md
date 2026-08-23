# ADR 0003 — Workspace as the persistence boundary

## Status

Accepted.

## Decision

Treat the workspace, not the Python process or Docker container, as the durable unit of user state.

## Context

Execution infrastructure will evolve from a single Docker container to multiple isolated containers and eventually managed execution. User data must survive those changes.

## Consequences

- Containers are disposable execution environments.
- Workspace storage is persistent.
- Workspace identity exists independently of runtime identity.
- MCP tools are workspace-aware from Phase 1 even though only one workspace exists.
- Future workspace routing can be introduced without changing the conceptual MCP API.
