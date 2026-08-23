# Python runtime

This image is the Phase 1 execution environment. It is intentionally separate from the MCP server.

Build it with:

```bash
docker build -t python-workspace-mcp-runtime:0.1 runtime/
```

Phase 1 does not yet provide the resource and network isolation guarantees planned for Phase 2.
