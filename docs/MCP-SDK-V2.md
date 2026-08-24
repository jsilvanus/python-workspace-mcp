# MCP SDK v2 baseline

This project targets the stable MCP Python SDK v2 (`mcp>=2,<3`) and the 2026-07-28 MCP protocol revision.

## Server architecture

The application uses `mcp.server.MCPServer`. Transport configuration is deliberately kept out of the server constructor. Streamable HTTP is created with `streamable_http_app()` and hosted by our ASGI/uvicorn layer.

The deployment is configured for JSON responses and stateless HTTP. Modern 2026-07-28 requests do not depend on MCP protocol sessions; the SDK transparently serves legacy MCP clients through the same Streamable HTTP endpoint.

## Authentication boundary

API-key authentication remains application-level Starlette middleware. It resolves an API key to a `Principal` and stores that request-scoped principal only for the duration of the HTTP request. Workspace authorization happens in the application layer.

This deliberately keeps authentication independent from MCP protocol sessions. A future OAuth/token-verifier integration can replace the API-key middleware without changing workspace ownership semantics.

## MCP primitives

- Tools perform Python execution and workspace operations.
- Resources are reserved for MCP-native file/resource delivery as the file subsystem is expanded.
- Custom HTTP routes are used only for non-MCP operational endpoints such as health checks and binary downloads.

## Explicitly not adopted

The project does not use the experimental Tasks API. The 2026-07-28 protocol moves Tasks into an extension and the SDK v2 core does not implement it.

## Compatibility

The SDK v2 Streamable HTTP application serves both modern 2026-07-28 clients and legacy handshake-era clients. We therefore do not maintain separate MCP server implementations or endpoints for those protocol eras.
