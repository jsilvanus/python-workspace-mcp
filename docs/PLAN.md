# Python Workspace MCP — Project Plan

## 1. Purpose

Python Workspace MCP provides AI agents with a persistent Python workspace for general computation and analysis through MCP.

The project is intentionally not limited to predefined statistics operations. An agent should be able to use Python for statistical analysis, data exploration, mathematics, simulations, visualization, scientific computing, file processing, and other legitimate computational tasks.

The central idea is:

> The AI decides what computation is useful; the workspace provides the Python environment in which that computation can be performed.

The project should remain useful as a small self-hosted deployment while also being capable of growing into a multi-user hosted service.

## 2. Core principles

1. **MCP is the interface.** The project is an MCP server first, not a web application with MCP added later.
2. **Streamable HTTP is the transport baseline.** The project is designed for remote MCP use from the beginning; do not make stdio the primary deployment architecture.
3. **The workspace is the durable abstraction.** Python processes and containers may be recreated; workspace data and identity persist.
4. **Execution is separated from MCP.** The MCP layer should not depend on a particular Python execution mechanism.
5. **One monorepo, multiple deployment profiles.** V1–V5 describe increasing deployment capabilities, not separate codebases.
6. **The core interface should remain stable.** Later deployment profiles should improve isolation, scale, and management without forcing MCP clients to learn a different conceptual API.
7. **Security is an explicit boundary.** AI-generated Python must eventually execute in a controlled environment rather than directly in the server process.
8. **Artifacts are first-class outputs.** Images, CSV files, spreadsheets, reports, and other generated files should be retrievable by the user.
9. **Open source throughout.** The project is intended to be published under the EUPL, subject to final license review.
10. **Build the smallest useful thing first.** Each phase should prove a real capability before adding infrastructure.

## 3. Deployment profiles

The project should provide named deployment profiles rather than separate V1/V2/V3 codebases.

| Profile | Purpose | Execution | Workspaces | Users |
|---|---|---|---|---|
| `local` | Minimal single-workspace deployment | Local Python | 1 | 1 |
| `isolated` | Multiple isolated workspaces | Docker | Multiple | 1 |
| `sandboxed` | Controlled execution | Docker + resource/security limits | Multiple | 1 |
| `self-hosted` | Complete self-hosted platform | Sandboxed containers | Multiple | Multiple |
| `hosted` | Managed SaaS | Sandboxed execution infrastructure | Multiple | Multiple |

The current codebase may continue to evolve while every supported profile remains available. For example, a current release may provide a `local` profile with the simplicity originally associated with V1.

## 4. Phase roadmap

### Phase 1 — Local proof of concept (`local`)

**Goal:** Prove that an AI can effectively use a persistent Python workspace through MCP.

Scope:

- Streamable HTTP MCP server.
- Single workspace.
- Single configured Python runtime.
- Persistent workspace directory.
- `execute_python` as the primary tool.
- Basic workspace/file access required by the agent.
- Scientific Python environment suitable for statistics and data analysis.
- Generated artifact discovery and retrieval.
- Basic authentication suitable for a single-user deployment.
- Basic execution/error reporting.
- Automated tests for MCP behavior and Python execution.

Likely Python packages:

- `numpy`
- `pandas`
- `scipy`
- `statsmodels`
- `sympy`
- `matplotlib`
- `seaborn`
- `openpyxl`

The exact package set should be configurable rather than permanently hard-coded into the architecture.

Non-goals:

- Multi-user identity management.
- Billing.
- Web UI.
- Production-grade sandboxing.
- Container orchestration.

Success criterion:

> A user can connect an MCP-capable AI to the server, provide data, ask for arbitrary analysis, and have the agent use persistent Python state/files and return useful results and artifacts.

### Phase 2 — Isolated multi-workspace (`isolated`)

**Goal:** Turn the prototype into a practical self-hosted service for one owner.

Scope:

- Docker-based Python execution.
- Multiple workspaces.
- Persistent volume per workspace.
- Workspace lifecycle management.
- Container lifecycle management.
- Workspace routing.
- Remote Streamable HTTP MCP remains the same external interface.
- Artifact service separated from Python execution.
- Configuration for Python runtime/image.
- Workspace deletion and recreation without losing the ability to recreate the execution environment.

Key architectural rule:

> Containers are disposable; workspace storage is persistent.

### Phase 3 — Sandboxed/resource-controlled execution (`sandboxed`)

**Goal:** Make execution suitable for AI-generated code and untrusted workloads within defined boundaries.

Scope:

- CPU limits.
- Memory limits.
- Disk/storage quotas.
- Execution timeouts.
- Process/PID limits.
- Restricted filesystem access.
- Non-root execution.
- Network disabled by default.
- Maximum stdout/stderr size.
- Maximum artifact size.
- Workspace-level configuration of limits.
- Security regression tests.
- Execution metadata and resource usage reporting.

The project must not imply that Docker alone makes arbitrary Python safe. The security model should explicitly document the assumptions, boundaries, and remaining risks.

### Phase 4 — Multi-user self-hosted platform (`self-hosted`)

**Goal:** Allow an administrator to operate the platform for multiple independent users.

Scope:

- User accounts.
- API key creation, rotation, and revocation.
- Authentication and authorization.
- User → workspace ownership.
- Workspace-level permissions.
- Web control-plane UI.
- Workspace creation/deletion/rename.
- File/artifact browsing and downloads.
- Resource usage visibility.
- Container status and restart controls.
- Administrative configuration.
- Audit/event records sufficient for administration and debugging.

The UI is a control plane. MCP remains the primary analysis interface.

### Phase 5 — Hosted SaaS (`hosted`)

**Goal:** Operate the same project as a commercial managed service.

Scope:

- Automated account/workspace provisioning.
- Subscription plans.
- Billing integration.
- Usage metering.
- Quotas.
- Automated suspension/resumption.
- Backups and recovery.
- Monitoring and alerting.
- Abuse controls.
- Operational administration.
- Customer-facing documentation and support workflows.
- Scalable execution infrastructure.

The hosted offering may use the same open-source codebase. The commercial value can be the managed infrastructure, reliability, convenience, support, and operational service rather than proprietary core functionality.

## 5. MCP interface direction

The initial interface should remain intentionally small.

### Primary operation

`execute_python(code)`

It should return structured execution information, including at minimum:

- success/failure status
- stdout
- stderr
- execution identifier
- generated artifacts when detectable

### Workspace/file operations

The exact MCP surface should be finalized during implementation, but the initial conceptual operations are:

- list files
- read/download files
- delete files where appropriate
- retrieve generated artifact information

Avoid exposing unnecessary filesystem primitives.

### Artifact model

Python should be able to create ordinary files inside the workspace, for example:

- PNG/JPEG/SVG plots
- CSV
- XLSX
- JSON
- PDF
- HTML
- ZIP
- generated reports

The execution layer reports artifacts; a separate artifact/file service is responsible for safe retrieval and, where appropriate, HTTP URLs.

## 6. Workspace model

A workspace is the persistent unit visible to the user and the AI.

Conceptually:

```text
Workspace
├── data
├── output
├── scratch
└── metadata
```

The exact layout is an implementation detail and may change.

The important lifecycle property is:

```text
workspace persists
container/process may not
```

This permits containers to be stopped, recreated, upgraded, or migrated without destroying user data.

## 7. Execution architecture

Keep the following layers separate:

```text
MCP transport/server
        ↓
Authentication / authorization
        ↓
Workspace service
        ↓
Execution service
        ↓
Python runtime
```

The Python execution implementation should be replaceable:

```text
local Python process
        ↓
Docker container
        ↓
sandboxed container
        ↓
managed execution infrastructure
```

The MCP contract should not need to change merely because the execution backend changes.

## 8. Artifact architecture

Artifacts should not be served directly by the Python process.

Preferred flow:

```text
Python
  ↓
workspace/output/file
  ↓
artifact manager
  ↓
metadata + authorization
  ↓
HTTP retrieval URL
```

For hosted deployments, URLs should normally be opaque and/or signed and should support expiration where appropriate.

The artifact system should support permissions and workspace ownership independently of the Python process.

## 9. Security model

The security model becomes increasingly important from Phase 2 onward.

Threats to consider include:

- accidental destructive Python
- infinite loops
- excessive CPU use
- excessive memory allocation
- excessive disk use
- process spawning
- filesystem escape
- network access
- access to host secrets
- cross-workspace access
- cross-user access
- malicious generated artifacts
- denial-of-service workloads

Security controls should be layered rather than relying on a single mechanism.

At minimum for sandboxed deployments:

- isolated execution environment
- least privilege
- restricted filesystem
- no host credentials
- network disabled by default
- resource limits
- execution timeout
- output limits
- per-workspace isolation
- authorization before artifact access

## 10. Observability

Each execution should eventually have a durable identifier and metadata such as:

- execution ID
- workspace ID
- user ID where applicable
- start/end time
- duration
- exit status
- resource usage
- generated artifacts
- error information

This supports debugging, security investigation, usage reporting, and later billing.

## 11. Testing strategy

Tests should be organized around stable contracts rather than deployment-specific implementation details.

### MCP contract tests

Verify that the same conceptual MCP operations behave consistently across deployment profiles.

### Execution tests

Cover:

- ordinary Python
- pandas/numpy/scipy operations
- statistical analysis
- plotting
- file creation
- exceptions
- timeouts
- large outputs
- generated artifacts

### Workspace tests

Cover:

- persistence
- isolation
- recreation
- deletion
- concurrent access where supported

### Security tests

Explicitly test attempted:

- filesystem escape
- network access
- process abuse
- resource exhaustion
- cross-workspace access
- cross-user access
- unauthorized artifact access

## 12. Repository structure

Use a monorepo. The structure should evolve gradually; do not create empty infrastructure for future phases merely for appearance.

Target structure:

```text
python-workspace-mcp/
├── apps/
│   ├── mcp/
│   ├── api/
│   ├── web/
│   └── worker/
├── packages/
│   ├── execution/
│   ├── workspace/
│   ├── artifacts/
│   ├── authentication/
│   ├── limits/
│   └── configuration/
├── runtimes/
│   └── python/
├── deployments/
│   ├── local/
│   ├── isolated/
│   ├── sandboxed/
│   ├── self-hosted/
│   └── hosted/
├── tests/
├── docs/
├── LICENSE
└── README.md
```

Do not force this entire structure into Phase 1. Extract packages when there is a real architectural need.

## 13. Planning/documentation structure

The `docs/` directory should be organized around decisions and stable concepts rather than chronological development notes.

Recommended structure:

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
     ├── 0003-workspace-as-persistence-boundary.md
     └── ...
```

### Document responsibilities

- `PLAN.md`: overall product direction, phases, scope, and success criteria.
- `ARCHITECTURE.md`: system components and their boundaries.
- `MCP-INTERFACE.md`: tools/resources and their behavioral contract.
- `DEPLOYMENT-PROFILES.md`: what each profile provides and how it is operated.
- `SECURITY.md`: threat model, sandbox assumptions, controls, and security requirements.
- `WORKSPACES.md`: workspace lifecycle, persistence, isolation, and storage model.
- `ARTIFACTS.md`: generated-file lifecycle, metadata, access, and URLs.
- `DEVELOPMENT.md`: local development, testing, release process, and contribution workflow.
- `ADRs/`: decisions that are important enough to preserve independently of the roadmap.

## 14. Versioning and releases

Do not use V1/V2/V3/V4/V5 as separate permanent code branches.

Use normal software versioning for releases and deployment profiles for capability selection.

For example:

```text
release 0.1 — local profile available
release 0.5 — isolated profile available
release 0.8 — sandboxed profile available
release 1.0 — self-hosted profile available
release 2.x — hosted service mature
```

The exact version numbers are not predetermined.

A later release should be able to improve the `local` profile without forcing it to become a multi-user deployment.

## 15. Open-source and licensing direction

The intended project license is EUPL, with the exact version and legal implications to be confirmed before the first public release.

The repository should distinguish:

- open-source project code
- deployment configuration
- optional hosted-service infrastructure
- third-party dependencies and their licenses

The project should not assume that the SaaS offering must be proprietary simply because it is commercial.

## 16. Immediate next step

Implement Phase 1 only.

The first milestone should establish:

1. a Python project and development environment;
2. a Streamable HTTP MCP server;
3. one persistent workspace;
4. `execute_python`;
5. basic file/artifact handling;
6. a useful scientific Python runtime;
7. configuration through environment variables/configuration files;
8. automated tests;
9. documentation showing how to connect an MCP client;
10. a clear boundary between the MCP server and the future execution service.

Do not implement Docker, multi-user accounts, billing, a web UI, or production resource orchestration in Phase 1 unless a small piece is strictly necessary to establish the architecture.

The success test is practical: connect an AI agent, give it real data, ask it to perform arbitrary analysis, and verify that it can iteratively use the persistent workspace and return useful artifacts.
