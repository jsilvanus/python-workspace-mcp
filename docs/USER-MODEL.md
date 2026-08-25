# User model

## Purpose

Phase 2 introduces the user concept without implementing a full account system. A user is the stable owner identity for workspaces and the future owner of API credentials.

## Phase 2 model

The server never creates a user on its own. Users only come into existence through an explicit CLI command:

```bash
python-workspace user add default "Default User"
```

```text
User: default / Default User
  |
  +-- Workspace A
  +-- Workspace B
```

The service's own identity — the user it resolves requests to when no per-user API key is presented — is configured with:

- `PYTHON_WORKSPACE_USER_ID`
- `PYTHON_WORKSPACE_USER_NAME`

That identity must be created via `python-workspace user add <id> <name>` (matching `PYTHON_WORKSPACE_USER_ID`/`PYTHON_WORKSPACE_USER_NAME`) before the server can serve any request for it; until then, MCP calls that fall back to it fail with `Unknown user`. The default workspace is still created automatically from `PYTHON_WORKSPACE_PATH` when no `PYTHON_WORKSPACE_WORKSPACES` are configured (see `docs/PHASE-2.md`), but it is only usable once its owning user exists.

Configured workspaces can optionally specify an owner as a fourth field:

```text
id:name:path:owner_user_id
```

The three-field form remains valid and assigns the configured service user as owner. That user still has to be created separately via the CLI.

## Authentication

Phase 2 retains the single Bearer API key configured by `PYTHON_WORKSPACE_API_KEY`. That key currently resolves to the configured service user, and resolution fails the same way if that user hasn't been created yet.

This is intentionally not a multi-user authentication system yet. Phase 3 will introduce real users, multiple credentials, credential management, roles and account administration.

## Authorization

Workspace access is owner-scoped internally now. MCP operations resolve the current user and reject workspaces owned by another user.

This establishes the authorization boundary before Phase 3 without prematurely exposing user administration through MCP.

## MCP surface

`get_user` returns the current stable user identity. `get_workspaces` lists only workspaces owned by that user. `get_workspace`, execution and file operations enforce workspace ownership.

The existing workspace-aware MCP API remains unchanged in shape.

## Design principle

The user is an identity/domain concept, not a UI concept. The web account system belongs to Phase 3; the ownership relationship belongs in the domain model now.
