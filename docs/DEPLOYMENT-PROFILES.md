# Deployment Profiles

Deployment profiles describe how much infrastructure and isolation is provided by a deployment. They are not separate products or permanent code branches.

## Profile overview

| Profile | Main use | Execution | Workspaces | Users | UI |
|---|---|---|---:|---:|---|
| `local` | Personal/local server | Docker-backed Python | 1 | 1 | No |
| `isolated` | Multiple isolated workspaces | Docker | Multiple | 1 | No |
| `sandboxed` | Controlled AI-generated execution | Docker + limits | Multiple | 1 | No |
| `self-hosted` | Multi-user installation | Sandboxed containers | Multiple | Multiple | Yes |
| `hosted` | Managed SaaS | Managed execution | Multiple | Multiple | Yes |

## Local

The Phase 1 profile.

Characteristics:

- Streamable HTTP MCP.
- One persistent workspace.
- One Docker-backed Python runtime/container.
- Runtime container may be recreated without intentionally deleting workspace data.
- Basic API-key protection for non-local use.
- Basic execution timeout.
- Not a hardened hostile-code sandbox.

This is the simplest useful deployment and should remain available as the project evolves.

## Isolated

Phase 2 adds multiple workspaces and stronger isolation/lifecycle management.

Characteristics:

- Multiple workspaces.
- Per-workspace persistent storage.
- Disposable execution containers.
- Workspace routing and lifecycle management.
- Same Streamable HTTP MCP interface.

## Sandboxed

Phase 2 also establishes explicit resource and security boundaries, potentially exposed as a stricter profile depending on deployment needs.

Expected controls include CPU, memory, disk, execution time, process/PID, filesystem, network, output and artifact limits.

## Self-hosted

Adds the multi-user control plane:

- Multiple users.
- Authentication and authorization.
- API-key management.
- User/workspace ownership.
- Web administration UI.
- Workspace and artifact management.
- Usage and container status.

## Hosted

The same system operated as a managed service:

- Account/workspace provisioning.
- Subscription plans and billing.
- Usage metering and quotas.
- Backups.
- Monitoring.
- Abuse controls.
- Scalable execution infrastructure.

## Compatibility principle

A user should be able to move from a simple profile to a more capable profile without changing the conceptual MCP workflow:

```text
connect → discover workspaces → select workspace → execute Python → inspect artifacts
```

## Versioning

Normal application versions are used for releases. Profiles are selected independently.

A later release can improve the `local` profile without turning it into a multi-user deployment.
