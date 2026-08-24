# ADR 0005: File transfer semantics

## Status

Accepted

## Decision

Use the workspace filesystem as the single source of truth. `read_file` is optimized for returning UTF-8 text to the AI. `get_file_url` is the transfer primitive for actual files, including binary files. `upload_file` is the MCP ingress primitive.

This avoids maintaining a separate artifact store for normal workspace outputs while still allowing clients to retrieve PDFs, images, spreadsheets and other binary files.