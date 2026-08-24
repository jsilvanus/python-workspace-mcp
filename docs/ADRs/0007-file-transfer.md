# ADR 0007: Workspace file transfer

## Status

Accepted

## Decision

Use the workspace filesystem as the single source of truth. `read_file` is an AI inspection operation for UTF-8 text. `upload_file` provides binary-safe MCP ingress. `get_file_url` provides signed client/user transfer for both text and binary files.

No separate artifact store is introduced in this phase.