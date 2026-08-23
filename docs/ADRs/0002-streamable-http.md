# ADR 0002 — Streamable HTTP as the primary MCP transport

## Status

Accepted.

## Decision

Use MCP Streamable HTTP as the primary transport from Phase 1 onward. Do not make stdio the primary deployment architecture.

## Context

The project is intended to evolve from a single-user deployment into a remote, multi-workspace, multi-user service. Starting with the eventual transport avoids a later protocol/deployment migration.

## Consequences

- The server is designed as an HTTP service from the beginning.
- Authentication and API-key handling are part of the initial architecture.
- Remote MCP clients are a first-class use case.
- Local deployment remains possible without requiring a separate stdio implementation.
