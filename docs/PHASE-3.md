# Phase 3 — Multi-user self-hosted deployment

Phase 3 turns the Phase 2 sandbox into a small self-hosted service that can be shared with friends. The first management UI is intentionally a CLI; a web UI is deferred.

## Goals

- Persistent users and API credentials
- Workspace ownership and per-request authorization
- Multiple users sharing one service without sharing workspaces
- CLI administration for users, API keys and workspaces
- Keep MCP API version 1 unchanged
- Keep the state layer replaceable for a future hosted/SaaS deployment

## Domain model

```text
API key → Principal → User → owned Workspaces → isolated Docker runtime
```

The MCP client never receives an administrator capability merely because it is authenticated. MCP operations are restricted to the authenticated user's workspaces.

## Persistent state

Phase 3 uses a small JSON state file configured with `PYTHON_WORKSPACE_STATE` (default `./data/state.json`). API keys are stored only as SHA-256 hashes. A generated raw key is printed once by the CLI.

The JSON store is deliberately a replaceable implementation boundary. It is suitable for a small self-hosted installation, not a claim that JSON is the right storage backend for SaaS.

## CLI

```text
python-workspace user add alice "Alice"
python-workspace user list
python-workspace user remove alice

python-workspace key create alice --label laptop
python-workspace key revoke <key>

python-workspace workspace create alice-data "Alice data" ./workspaces/alice alice
python-workspace workspace list
python-workspace workspace remove alice-data
```

`key create` prints the secret once. Store it securely; the server cannot recover it from the hash.

## Authentication

Set `PYTHON_WORKSPACE_REQUIRE_AUTH=true` for a shared installation. Clients authenticate with:

```text
Authorization: Bearer <api-key>
```

The existing `PYTHON_WORKSPACE_API_KEY` remains supported as a compatibility/bootstrap mechanism and maps to the configured service user.

## Security boundary

The authenticated user is resolved before MCP processing. Workspace operations verify ownership. File artifact URLs use a separate server signing secret configured with `PYTHON_WORKSPACE_FILE_SIGNING_SECRET`.

Phase 3 does not yet provide registration, password login, roles, an admin web UI, billing, or SaaS account management.

## Example friend setup

1. Administrator starts the service with authentication required.
2. Administrator creates a user with the CLI.
3. Administrator creates a workspace owned by that user.
4. Administrator creates an API key for the user.
5. User configures the API key in their MCP client.
6. The user can see and operate only their own workspaces.

## Future web UI

A future UI should call the same management/domain services rather than modifying state files directly. This keeps CLI and web administration as two frontends to the same control plane.
