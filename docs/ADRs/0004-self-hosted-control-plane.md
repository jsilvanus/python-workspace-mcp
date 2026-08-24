# ADR 0004 — Self-hosted control plane starts as a CLI

## Status

Accepted for Phase 3.

## Context

The project is intended to let a small group of people use persistent Python workspaces through their AI/MCP clients. A web UI is useful for administration, but it is not necessary to prove the multi-user service model.

## Decision

Phase 3 introduces a persistent self-hosted control plane with:

- users;
- hashed API keys;
- workspace ownership;
- per-request authentication and authorization;
- a CLI for administration.

The CLI is the first UI. The future web UI will call the same domain/control-plane services rather than directly editing state.

A small JSON state store is the initial persistence implementation. It is an implementation detail and may later be replaced by a database without changing the MCP application contract.

## Consequences

- Friends can be provisioned without building a web application first.
- The authentication and ownership boundaries are tested before adding browser UX.
- The CLI is useful for server administration and automation.
- JSON persistence is intentionally suitable only for a small self-hosted installation; SaaS should use a stronger persistent backend.
- MCP remains the analysis interface, while the control plane handles accounts, credentials and workspaces.
