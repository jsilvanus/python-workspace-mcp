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
- CPU limits.
- Memory limits.
- PID/process limits.
- Execution timeouts.
- Application-level storage quotas.
- stdout/stderr size limits.
- Artifact-count limits.
- Workspace-scoped artifact URLs.
- Resource metadata in execution responses.
- Security and cross-workspace regression tests.

Default Phase 2 limits:

```text
CPU:                    2 cores
Memory:                 4 GiB
Workspace storage:      10 GiB
Execution timeout:      60 s
PIDs:                   128
stdout/stderr:          2 MiB
Artifacts/execution:    50
```

**Explicit limitation:** storage is currently an application-level quota rather than a guaranteed hard filesystem quota. A future backend can provide hard quotas where the storage/runtime supports them.

**Success criterion:** two or more configured workspaces can execute independently, persist their own files, use separate runtime containers, and remain within configured CPU/memory/PID/time/output controls. Cross-workspace file access must fail.

### Phase 3 — Multi-user self-hosted (`self-hosted`)

- User accounts.
- Authentication and authorization.
- API key creation/rotation/revocation.
- User → workspace ownership and permissions.
- Web control-plane UI.
- Workspace/file/artifact management.
- Resource/status visibility.
- Administration and audit/event records.

MCP remains the primary analysis interface; the UI is a control plane.

### Phase 4 — Hosted/SaaS (`hosted`)

- Managed provisioning.
- Subscription plans and billing.
- Usage metering and quotas.
- Automatic suspension/resumption.
- Backups and recovery.
- Monitoring and alerting.
- Abuse controls.
- Scalable execution infrastructure.
- Customer administration and support workflows.

The hosted service may use the same open-source codebase; commercial value can be managed infrastructure, reliability, support and convenience.

## Stable MCP interface

The contract is workspace-aware even when Phase 1 has one workspace.

### Discovery/management

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

The external MCP contract remains API version `1` through Phase 2.

## Testing strategy

### Phase 2 isolation

- Multiple configured workspaces.
- Independent container names.
- Independent persistent directories.
- Cross-workspace path rejection.
- Network unavailable inside runtime.
- Non-root execution.
- Read-only runtime filesystem.
- CPU/memory/PID limits are passed to Docker correctly.
- Execution timeout.
- Output truncation.
- Artifact-count limiting.
- Storage quota behavior.
- Container recreation without data loss.

## Current development status

Phase 2 is being developed on the `phase-2` branch. The no-shell development goal is to complete the implementation, contract, tests and documentation as far as possible. Docker runtime behavior and actual resource enforcement require a real runtime for final validation.
