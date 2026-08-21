# Deployment Profiles

Deployment profiles describe how much infrastructure and isolation is provided by a deployment. They are not separate products or permanent code branches.

## Profile overview

| Profile | Main use | Execution | Workspaces | Users | UI |
|---|---|---|---:|---:|---|
| `local` | Personal/local server | Local Python | 1 | 1 | No |
| `isolated` | Small self-hosted service | Docker | Multiple | 1 | No |
| `sandboxed` | Safer AI-generated execution | Docker + limits | Multiple | 1 | No |
| `self-hosted` | Multi-user installation | Sandboxed containers | Multiple | Multiple | Yes |
| `hosted` | Managed SaaS | Managed execution | Multiple | Multiple | Yes |

## Local

The smallest supported deployment.

Characteristics:

- Streamable HTTP MCP.
- One workspace.
- Local Python runtime.
- Persistent local workspace directory.
- Basic API-key protection suitable for a trusted single-user environment.
- No Docker requirement.

This is the profile corresponding conceptually to the original V1 idea.

It should remain available even after more advanced profiles exist.

## Isolated

Adds workspace isolation through Docker.

Characteristics:

- Multiple workspaces.
- One persistent volume per workspace.
- Disposable execution containers.
- Workspace lifecycle management.
- Same Streamable HTTP MCP interface.

A container may be recreated without destroying workspace data.

## Sandboxed

Adds explicit resource and security boundaries.

Expected controls include:

- CPU quota.
- Memory quota.
- Disk quota.
- Execution timeout.
- Process limits.
- Non-root execution.
- Restricted filesystem.
- Network disabled by default.
- Output and artifact size limits.

This profile is the minimum intended basis for running arbitrary AI-generated Python for users who should not be trusted with the host system.

## Self-hosted

Adds the control plane needed by an organization or administrator.

Expected features:

- Multiple users.
- Authentication.
- API-key management.
- User/workspace ownership.
- Web administration UI.
- Workspace management.
- Artifact browsing/downloads.
- Usage information.
- Container status and lifecycle controls.

## Hosted

The same system operated as a managed service.

Expected additions:

- Account provisioning.
- Subscription plans.
- Billing.
- Usage metering.
- Quotas.
- Automated workspace provisioning.
- Backups.
- Monitoring.
- Abuse controls.
- Scalable execution infrastructure.

The hosted profile is a deployment/service model, not a separate implementation of the MCP concept.

## Compatibility principle

A user should be able to move from a simple profile to a more capable profile without changing the conceptual MCP workflow.

For example:

```text
local → isolated → sandboxed → self-hosted → hosted
```

The MCP client should continue to see the same fundamental concepts:

```text
connect → select workspace → execute Python → inspect artifacts
```

## Versioning

Normal application versions should be used for releases. Profiles should be selected independently.

For example, a future release may provide:

```text
python-workspace-mcp 0.x
  ├── local
  ├── isolated
  └── sandboxed
```

while a later release may provide:

```text
python-workspace-mcp 1.x
  ├── local
  ├── isolated
  ├── sandboxed
  └── self-hosted
```

A release can improve the `local` profile without turning it into a multi-user system.
