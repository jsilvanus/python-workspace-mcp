# Phase 4 — packages and file transfer

Phase 4 adds controlled package installation and first-class workspace file ingress/egress.

## Scope

- Keep ordinary Python execution completely offline.
- Allow selected resource profiles to install packages from PyPI.
- Persist installed packages with the workspace.
- Add binary-safe file upload through MCP.
- Keep `read_file` for AI text inspection.
- Keep signed `get_file_url` for actual file transfer, including PDFs/images/archives.
- Make package installation, file upload and file download explicit workspace capabilities.

## Non-goals

- Arbitrary outbound Internet access.
- User-selectable arbitrary package indexes.
- A general web proxy.
- Package installation through the base image.

## Security note

The current implementation uses a short-lived Docker installer with network access and pins pip to the PyPI simple index. The long-lived execution container remains `network=none`. This is an application-level restriction; a future package proxy is recommended for stronger network-level enforcement.
