# Architecture

Python Workspace MCP is organized around a stable MCP/workspace contract and replaceable execution infrastructure.

## Core architecture

```text
MCP client / AI
      │
      ▼
Streamable HTTP MCP server
      │
      ▼
Authentication
      │
      ▼
Workspace service
      │
      ▼
Execution backend
      │
      ▼
Python runtime
      │
      ▼
Persistent workspace storage
```

The MCP server must not become tightly coupled to one Python execution implementation.

## Workspace as persistence boundary

A workspace is the durable unit of user data.

```text
workspace persists
container/process may not
```

This lets execution environments be stopped, recreated, upgraded or moved without destroying user work.

## Deployment evolution

### Local — Phase 1

```text
HTTP MCP
   │
   ▼
Single Workspace
   │
   ▼
Docker Python container
   │
   ▼
Persistent host workspace
```

### Isolated + sandboxed — Phase 2

```text
HTTP MCP
   │
   ▼
Workspace router
   │
   ├── Workspace A → isolated container + persistent storage
   ├── Workspace B → isolated container + persistent storage
   └── Workspace C → isolated container + persistent storage

Execution layer additionally enforces CPU/RAM/disk/PID/time/network/filesystem limits.
```

### Self-hosted — Phase 3

```text
HTTP MCP
   │
   ▼
Authentication / authorization
   │
   ▼
User / Workspace routing
   │
   ▼
Sandboxed execution service
```

### Hosted — Phase 4

The same logical architecture is operated as a managed service with provisioning, quotas, metering, billing, monitoring and scalable execution infrastructure.

## Monorepo boundary

The project is one monorepo. Deployment profiles are configurations/compositions of shared capabilities, not separate projects.

Target capabilities include:

- MCP server
- workspace service
- execution service
- artifact service
- authentication/authorization
- resource limiting
- web control plane
- background worker/scheduler

They should become separate packages/services only when an independent lifecycle or security boundary justifies it.

## Transport

Streamable HTTP is the primary MCP transport from the first implementation. Do not design the core around stdio and retrofit HTTP later.

## Execution boundary

Define an execution abstraction accepting code plus workspace context and returning structured results.

```text
ExecutionRequest
├── workspace_id
├── code
└── execution options

ExecutionResult
├── status
├── stdout
├── stderr
├── duration
├── execution_id
└── artifacts
```

Phase 1 implements this boundary with a Docker execution backend. Later profiles can add multi-workspace containers, stronger sandboxing or remote execution workers.

## Artifact boundary

```text
Python
  ↓
workspace file
  ↓
artifact metadata
  ↓
authorized HTTP retrieval
```

Artifact access is separate from Python's execution behavior.

## Future scaling boundary

The architecture leaves room for:

```text
MCP gateway
     │
     ▼
workspace scheduler
     │
     ├── execution worker A
     ├── execution worker B
     └── execution worker C
```

A persistent workspace can be attached to whichever execution worker is selected.

## Architectural invariants

1. Streamable HTTP is the primary MCP transport.
2. Workspace identity is independent of container identity.
3. Workspace storage is persistent while execution environments are disposable.
4. MCP transport is independent of Python execution implementation.
5. Artifact access is authorized independently of Python code.
6. User/workspace isolation is enforced below the model/agent layer.
7. Resource limits are enforced by execution infrastructure, not Python conventions.
8. Deployment profiles share the same conceptual APIs and core components.
