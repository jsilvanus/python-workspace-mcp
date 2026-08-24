# Python Workspace MCP — Project Plan

## Purpose

Give AI agents a persistent Python workspace for statistics, data analysis, mathematics, simulations, visualization, scientific computing and general computation through MCP.

> The AI decides what computation is useful; the workspace provides the Python environment in which it can be performed.

## Core principles

1. MCP is the interface.
2. Streamable HTTP is the transport baseline from Phase 1; stdio is not the primary architecture.
3. The workspace is the durable abstraction; runtime processes/containers may be recreated.
4. MCP is separated from execution backends.
5. One monorepo, multiple deployment profiles.
6. The MCP contract should remain stable as capabilities grow.
7. Phase 1 is not a hostile-code sandbox; Phase 2 provides the stronger isolation and limits.
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

**Goal:** prove the complete remote MCP workflow with one persistent Docker-backed Python workspace.

Scope:

- Streamable HTTP MCP server.
- One workspace, with workspace-aware API from day one.
- Docker Python runtime.
- Persistent workspace directory mounted into the runtime container.
- Disposable runtime container; persistent workspace data.
- `execute_python`.
- `get_workspaces` — exactly one workspace initially.
- `get_workspace`.
- `get_system_info`.
- Basic file operations.
- Artifact discovery and HTTP retrieval.
- Optional Bearer API-key authentication; strongly recommended for non-local use.
- Execution timeout.
- Execution IDs and structured status/stdout/stderr/artifacts.
- Scientific Python runtime: numpy, pandas, scipy, statsmodels, sympy, matplotlib, seaborn, openpyxl.
- Automated unit/contract tests.
- Deployment documentation.

**Explicit limitations:** no multi-workspace scheduling, CPU/RAM/disk/PID quotas, network isolation, or production-grade hostile-code sandboxing.

**Success criterion:** an MCP client connects over Streamable HTTP; an agent can inspect its workspace, execute arbitrary analysis Python, persist/read data, create and retrieve useful artifacts, and retain workspace data after the runtime container is recreated.

### Phase 2 — Multi-workspace isolation + resource controls (`isolated` / `sandboxed`)

- Multiple workspaces.
- Per-workspace Docker containers and persistent storage.
- Workspace routing and lifecycle.
- Container recreation without data loss.
- CPU limits.
- Memory limits.
- Storage/disk quotas.
- Execution timeouts.
- PID/process limits.
- stdout/stderr and artifact size limits.
- Restricted filesystem access.
- Non-root execution.
- Network disabled by default.
- Workspace-level limit configuration.
- Security regression tests.
- Execution/resource metadata.

The Phase 1 MCP contract remains the external foundation; `get_workspaces` becomes genuinely multi-workspace.

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

Workspace IDs are accepted now so later profiles can activate multiple workspaces without changing tool concepts. Phase 1 may default them to its sole workspace.

### Versioning

Distinguish:

- **server version** — software release;
- **API version** — MCP application contract;
- **deployment profile** — capability/infrastructure level.

Example:

```text
server_version: 0.1.0
api_version: 1
deployment_profile: local
transport: streamable-http
```

## Workspace model

A workspace is the persistent unit visible to the AI/user. The invariant is:

```text
workspace persists
runtime container/process may not
```

## Execution architecture

```text
MCP transport/server
        ↓
Authentication
        ↓
Workspace service
        ↓
Execution backend
        ↓
Python runtime
```

The execution backend can evolve from a single Docker runtime to multi-workspace containers, sandboxed execution, and managed infrastructure without changing the MCP contract.

## Artifact architecture

```text
Python
  ↓
workspace file
  ↓
artifact metadata
  ↓
authorized HTTP retrieval
```

Artifact URLs should be opaque/signed where appropriate. Artifact authorization must be independent of Python execution.

## Security direction

Phase 1 establishes a basic boundary but is **not** a hardened sandbox. Docker alone must not be presented as sufficient protection for arbitrary hostile Python.

Phase 2 adds layered controls for filesystem escape, host credential exposure, network access, process abuse, resource exhaustion, cross-workspace access and unauthorized artifact access.

## Observability

Execution records should eventually contain execution ID, workspace ID, user ID where applicable, timestamps, duration, exit status, resource usage, artifacts and errors. Phase 1 establishes execution IDs and basic execution metadata.

## Testing strategy

### MCP
- Streamable HTTP initialization.
- Tool discovery and invocation.
- Workspace-aware parameters.

### Execution
- Ordinary Python.
- numpy/pandas/scipy.
- Statistical analysis.
- Plotting.
- File creation/modification.
- Exceptions.
- Timeouts.
- Artifacts.

### Workspace
- Persistence.
- Path containment.
- Container recreation.
- File operations.

### Phase 2 security
- Filesystem escape.
- Network access.
- Process abuse.
- Resource exhaustion.
- Cross-workspace access.
- Artifact authorization.

## Documentation structure

```text
docs/
├── PLAN.md
├── ARCHITECTURE.md
├── MCP-INTERFACE.md
├── DEPLOYMENT-PROFILES.md
├── SECURITY.md
├── WORKSPACES.md
├── ARTIFACTS.md
├── DEVELOPMENT.md
└── ADRs/
    ├── 0001-monorepo-and-deployment-profiles.md
    ├── 0002-streamable-http.md
    └── 0003-workspace-as-persistence-boundary.md
```

Do not create future-phase infrastructure merely for appearance.

## Current development status

Phase 1 is being developed on the `phase-1` branch. The no-shell development goal is to complete code, stable contract, tests and documentation as far as possible. Docker and end-to-end MCP execution must be validated with a real runtime before Phase 1 is considered complete.
