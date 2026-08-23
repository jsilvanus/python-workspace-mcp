# Development

## Phase 1

The current implementation is developed on the `phase-1` branch.

Requirements:

- Python 3.11+
- Docker
- an MCP client supporting Streamable HTTP

Install the Python project in an isolated environment and build the runtime image from `runtime/Dockerfile`.

The server exposes `/mcp` and `/healthz`.

## Development rule

Keep MCP protocol concerns, workspace management, execution backends and artifact retrieval separated. Do not add future multi-user infrastructure merely for appearance.

## Validation boundary

Code, tests and documentation can be developed without a Docker runtime, but Phase 1 cannot be declared complete until the actual Docker image, MCP connection, Python execution, artifact retrieval and container recreation/persistence have been exercised end-to-end.
