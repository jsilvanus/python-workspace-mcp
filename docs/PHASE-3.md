# Phase 3 — Multi-user self-hosted deployment

Phase 3 turns the Phase 2 sandbox into a small self-hosted service that can be shared with friends. The first management UI is intentionally a CLI; a web UI is deferred.

## Goals

- Persistent users and API credentials
- Workspace ownership and per-request authorization
- Multiple users sharing one service without sharing workspaces
- Administrator-controlled named resource profiles
- Default and maximum resource levels per profile
- Profile assignment when creating a workspace
- Bounded on-demand CPU/memory/time/PID/output/artifact resources per execution
- CLI administration for users, API keys, workspaces and resource profiles
- Keep MCP API version 1 stable; additive optional execution resources only
- Keep the state layer replaceable for a future hosted/SaaS deployment

## Domain model

```text
API key → Principal → User → owned Workspaces → Resource Profile → isolated Docker runtime
                                                   ↑
                                            admin-controlled policy
```

The MCP client never receives an administrator capability merely because it is authenticated. MCP operations are restricted to the authenticated user's workspaces. A client can request additional execution resources only within the maximums of the workspace's assigned profile.

## Resource profiles

Each profile contains **defaults** and **maximums**. Defaults are used when an execution does not request additional resources. Maximums are hard ceilings and are never controlled by the MCP client.

Built-in profiles are `small`, `standard`, and `large`. Administrators can create additional profiles through the CLI.

Workspace creation selects a profile:

```text
python-workspace workspace create bob-data "Bob data" ./workspaces/bob bob --profile standard
```

An administrator can change the profile later. The AI cannot change the workspace profile.

For an individual execution, `execute_python` may receive an optional `resources` object. Requested CPU, memory, timeout, PID, output and artifact limits are validated against the profile maximums. Storage remains a persistent workspace policy. Runtime CPU/memory/PID settings are updated for the execution and execution is serialized per workspace to prevent concurrent limit changes from interfering.

## Persistent state

Phase 3 uses a small JSON state file configured with `PYTHON_WORKSPACE_STATE` (default `./data/state.json`). API keys are stored only as SHA-256 hashes. A generated raw key is printed once by the CLI. Resource profiles and workspace profile assignments are persisted in the same state store.

The JSON store is deliberately a replaceable implementation boundary. It is suitable for a small self-hosted installation, not a claim that JSON is the right storage backend for SaaS.

## CLI

```text
python-workspace user add alice "Alice"
python-workspace user list
python-workspace user remove alice

python-workspace key create alice --label laptop
python-workspace key revoke <key>

python-workspace profile list
python-workspace profile show standard
python-workspace profile create researcher "Researcher" --cpu 2 --memory-gb 8 --storage-gb 25 --max-cpu 4 --max-memory-gb 16
python-workspace profile remove researcher

python-workspace workspace create alice-data "Alice data" ./workspaces/alice alice --profile standard
python-workspace workspace set-profile alice-data large
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

The authenticated user is resolved before MCP processing. Workspace operations verify ownership. Resource profiles are administrator-controlled policy; an AI cannot elevate a workspace's profile or maximums. File artifact URLs use a separate server signing secret configured with `PYTHON_WORKSPACE_FILE_SIGNING_SECRET`.

Phase 3 does not yet provide registration, password login, roles, an admin web UI, billing, or SaaS account management.

## Example friend setup

1. Administrator starts the service with authentication required.
2. Administrator creates a resource profile or selects a built-in profile.
3. Administrator creates a user with the CLI.
4. Administrator creates a workspace owned by that user and assigns the profile.
5. Administrator creates an API key for the user.
6. User configures the API key in their MCP client.
7. The user can see and operate only their own workspaces and can request additional execution resources only up to the profile maximum.

## Future web UI

A future UI should call the same management/domain services rather than modifying state files directly. This keeps CLI and web administration as two frontends to the same control plane.
