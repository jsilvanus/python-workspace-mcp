# ADR 0001: Monorepo and Deployment Profiles

- **Status:** Accepted
- **Date:** 2026-08-21

## Context

The project is intended to evolve from a very small single-workspace MCP server into a potentially multi-user hosted service.

The initial roadmap described this as V1 through V5. Treating those stages as separate codebases would create duplicated execution, workspace, security, and MCP logic and make it difficult to keep fixes synchronized.

At the same time, users may have very different deployment needs. A person who only wants one personal Python workspace should not need to operate the infrastructure required by a multi-user SaaS platform.

## Decision

Use one monorepo and maintain multiple **deployment profiles**.

The initial profiles are:

1. `local`
2. `isolated`
3. `sandboxed`
4. `self-hosted`
5. `hosted`

The codebase continues to evolve normally. Deployment profiles select the amount of infrastructure, isolation, authentication, and management appropriate to the deployment.

V1–V5 therefore describe the project's capability progression, not separate repositories or long-lived implementation branches.

## Consequences

### Positive

- Security and correctness fixes can benefit all profiles.
- The MCP interface can remain stable.
- Users can choose a deployment appropriate to their needs.
- The simple deployment remains available even as the platform becomes more sophisticated.
- Hosted and self-hosted deployments can share the same core implementation.
- Architectural boundaries become explicit early.

### Negative

- The monorepo needs clear package and deployment boundaries.
- Some abstractions must be designed before all deployment profiles exist.
- Documentation must distinguish application versions from deployment profiles.

## Related decisions

- Streamable HTTP is the primary MCP transport from the first implementation.
- Workspace identity is independent from Python process/container identity.
- Execution is separated from MCP transport.
