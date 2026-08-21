# Architecture

This document describes the intended architectural boundaries of Python Workspace MCP. It is deliberately broader than the initial implementation; future components should be introduced when their deployment profile requires them.

## Core principle

The MCP interface and Python execution environment are separate concerns.

```text
MCP client / AI
      │
      ▼
Streamable HTTP MCP server
      │
      ▼
Authentication / authorization
      │
      ▼
Workspace service
      │
      ▼
Execution service
      │
      ▼
Python runtime
      │
      ▼
Persistent workspace storage
```

The execution backend may evolve without changing the fundamental workspace or MCP concepts.

## Workspace as the persistence boundary

A workspace is the durable unit of user data and state.

```text
Workspace
├── input/data
├── output/artifacts
├── scratch
└── metadata
```

A Python process or container is disposable. Workspace data is not.

This allows execution environments to be stopped, recreated, upgraded, or moved without destroying the user's work.

## Deployment evolution

### Local

```text
HTTP MCP
   │
   ▼
Workspace
   │
   ▼
Local Python
```

### Isolated

```text
HTTP MCP
   │
   ▼
Workspace router
   │
   ├── Workspace A → Docker container + volume
   ├── Workspace B → Docker container + volume
   └── Workspace C → Docker container + volume
```

### Sandboxed

The isolated architecture gains explicit resource and security boundaries.

### Self-hosted

```text
HTTP MCP
   │
   ▼
Authentication
   │
   ▼
User / Workspace routing
   │
   ▼
Execution service
   │
   └── sandboxed containers
```

### Hosted

The same logical architecture is operated as a service, with provisioning, quotas, metering, billing, monitoring, and scalable execution infrastructure around it.

## Monorepo boundary

The project is one monorepo. Deployment profiles are configurations and compositions of the same core capabilities, not separate projects.

Target components:

- MCP server
- workspace service
- execution service
- artifact service
- authentication/authorization
- resource limiting
- web control plane
- background worker/scheduler

These should become separate packages/services only when their independent lifecycle or security boundary justifies it.

## Transport

Streamable HTTP is the project transport baseline from the first implementation. The project is intended to be remotely accessible from the beginning.

Do not design the core around a stdio-only process and retrofit HTTP later.

## Execution boundary

The MCP server must not become tightly coupled to Python subprocess details.

Define an execution abstraction capable of accepting code plus workspace context and returning structured results.

Conceptually:

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

Phase 1 may implement this with a local Python process. Later profiles can implement it using containers or a remote execution service.

## Artifact boundary

Generated files should be handled independently from Python's HTTP serving behavior.

```text
Python
  ↓
workspace file
  ↓
artifact manager
  ↓
metadata / authorization
  ↓
HTTP retrieval
```

The artifact service owns safe access to generated files.

## Future scaling boundary

Do not prematurely introduce distributed infrastructure in the local profile. However, the architecture should leave room for:

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

A persistent workspace can then be attached to whatever execution worker is selected.

## Architectural invariants

The following should remain true as the project evolves:

1. Streamable HTTP is the primary MCP transport.
2. Workspace identity is independent of container identity.
3. Workspace storage is persistent even when execution environments are disposable.
4. MCP transport is independent of Python execution implementation.
5. Artifact access is authorized independently of Python code.
6. User/workspace isolation is enforced below the model/agent layer.
7. Resource limits are enforced by the execution infrastructure, not merely by Python conventions.
8. Deployment profiles share the same conceptual APIs and core components.
