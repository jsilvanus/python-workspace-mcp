# Python Workspace MCP — Project Plan

## Purpose

Give AI agents a persistent Python workspace for statistics, data analysis, mathematics, simulations, visualization, scientific computing and general computation through MCP.

> The AI decides what computation is useful; the workspace provides the Python environment in which it can be performed.

## Core principles

1. MCP is the interface.
2. Streamable HTTP is the transport baseline; stdio is not the primary architecture.
3. The workspace is the durable abstraction; runtime processes/containers may be recreated.
4. MCP is separated from execution backends.
5. One monorepo, multiple deployment profiles.
6. The MCP contract should remain stable as capabilities grow.
7. Phase 1 is not a hostile-code sandbox; Phase 2 adds layered isolation and limits.
8. Artifacts are first-class outputs.
9. Intended open-source license: EUPL, subject to final legal review.
10. Build the smallest useful thing first.
11. Identity and ownership are domain concepts, independent of the future web UI.
12. The control plane may evolve independently of the MCP analysis interface.

## Deployment profiles

| Profile | Purpose | Execution | Workspaces | Users |
|---|---|---|---|---|
| `local` | Minimal useful deployment | Docker-backed Python | 1 | 1 |
| `isolated` | Multiple isolated workspaces | Docker | Multiple | 1 |
| `sandboxed` | Controlled execution | Docker + resource/security limits | Multiple | 1 |
| `self-hosted` | Multi-user platform | Sandboxed containers | Multiple | Multiple |
| `hosted` | Managed SaaS | Managed sandboxed execution | Multiple | Multiple |

Profiles are not separate repositories or frozen software versions.

## Phases

### Phase 0 — Architecture & foundation

- Monorepo and repository conventions.
- Stable MCP/API design.
- Streamable HTTP decision.
- Workspace as persistence boundary.
- Execution/backend boundary.
- Planning and ADR documentation.

### Phase 1 — Docker-backed single workspace (`local`)

Phase 1 is merged into `main`. It establishes the Streamable HTTP MCP server, workspace-aware API, Docker execution, persistence, file/artifact handling, API-key support, execution IDs and basic timeout handling.

Phase 1 remains pending real Docker/MCP end-to-end validation before being considered production-ready.

### Phase 2 — Multi-workspace isolation + resource controls (`isolated` / `sandboxed`)

**Goal:** provide multiple persistent workspaces with one isolated Docker runtime per workspace and configurable execution/resource limits, without changing MCP API version 1.

Implementation scope:

- Configuration-backed multiple workspaces.
- Stable workspace IDs and routing.
- One persistent workspace directory per workspace.
- One disposable Docker container per workspace.
- Container lifecycle and recreation.
- Non-root runtime.
- Network disabled by default.
- Dropped Linux capabilities.
- `no-new-privileges`.
- Read-only runtime filesystem except workspace and bounded `/tmp`.
- CPU, memory, PID, execution-time, output and artifact limits.
- Application-level storage quotas.
- Workspace-scoped artifact URLs.
- Resource metadata in execution responses.
- Minimal user identity and workspace ownership model.
- A single configured user in the Phase 2 deployment.

### Phase 3 — Multi-user self-hosted (`self-hosted`)

**Goal:** make the service genuinely useful for a small group of people, such as the author's friends, without requiring a web UI yet.

Implementation scope:

- Persistent user registry.
- Persistent API-key registry with hashed secrets.
- API-key → principal → user resolution per HTTP request.
- Multiple users sharing one service.
- Workspace ownership and authorization enforced for every MCP workspace operation.
- CLI control plane for user management.
- CLI API-key creation/revocation.
- CLI workspace creation/listing/removal.
- Persistent workspace ownership rather than environment-only ownership.
- Authentication-required deployment mode.
- Per-user workspace visibility.
- User/workspace discovery through the existing MCP API.
- Documentation for a small shared self-hosted installation.
- Tests for persistence, authentication and ownership boundaries.

The first UI is deliberately **CLI**. A web control-plane UI is deferred until there is a real need for it.

The CLI is an administration/control interface, not a replacement for MCP. Friends still use their AI/MCP client for Python work.

### Phase 4 — Hosted/SaaS (`hosted`)

- Managed provisioning.
- Subscription plans and billing.
- Usage metering and quotas.
- Automatic suspension/resumption.
- Backups and recovery.
- Monitoring and alerting.
- Abuse controls.
- Scalable execution infrastructure.
- Web control-plane UI.
- Customer administration and support workflows.

The hosted service may use the same open-source codebase; commercial value can be managed infrastructure, reliability, support and convenience.

## Stable MCP interface

The contract is workspace-aware even when Phase 1 has one workspace.

### Discovery/management

- `get_user()` — stable identity of the current caller.
- `get_workspaces()` — list workspaces visible to the caller.
- `get_workspace(workspace_id?)` — workspace information.
- `get_system_info()` — server/API version, deployment profile, runtime/capabilities and limits.

### Computation

- `execute_python(code, workspace_id?)` — execute code and return structured execution information.

### Files/artifacts

- `list_files(workspace_id?, path?)`
- `read_file(path, workspace_id?)`
- `delete_file(path, workspace_id?)`
- `get_file_url(path, workspace_id?)`

Workspace IDs are accepted now so later profiles can activate multiple workspaces without changing tool concepts.

## Versioning

Distinguish:

- **server version** — software release;
- **API version** — MCP application contract;
- **deployment profile** — capability/infrastructure level.

The external MCP contract remains API version `1` through Phase 3.

## Testing strategy

### Phase 3 identity and control plane

- Multiple persistent users.
- API keys are never persisted in plaintext.
- Generated API keys authenticate the correct user.
- Revoked keys stop authenticating.
- Users survive service restart.
- Workspaces survive service restart.
- User cannot access another user's workspace.
- User sees only owned workspaces through MCP.
- User cannot delete another user's files through MCP.
- CLI creates and removes users/workspaces as intended.
- User deletion is blocked while owned workspaces remain.

## Current development status

Phase 3 is being developed on the `phase-3` branch. The implementation includes the persistent user/workspace state layer, per-request API-key identity, ownership enforcement and CLI control plane. It has not yet been runtime-validated; real Docker/MCP integration testing still requires a shell/runtime.
