# ADR 0003: Introduce a user domain model before multi-user accounts

## Status

Accepted

## Context

Phase 2 introduces multiple persistent workspaces and ownership/isolation, while full multi-user account management is scheduled for Phase 3. Waiting until Phase 3 to introduce users would make workspace ownership an architectural retrofit.

## Decision

Introduce a minimal `User` and `Principal` domain model in Phase 2.

Phase 2 has one configured user by default. The existing single Bearer API key resolves to that user. Workspaces have an owner user ID and access is owner-scoped internally.

Expose `get_user` so an MCP client can discover the stable identity it is operating as.

Do not implement registration, multiple credentials, roles, account management or a web UI yet.

## Consequences

- Workspace ownership is part of the model before Phase 3.
- The MCP API remains workspace-oriented and does not need a user ID on every operation.
- Phase 3 can replace the single-user registry with a persistent multi-user identity store and richer authentication without changing workspace semantics.
- Phase 2 remains intentionally simple and is not a complete account-management system.
