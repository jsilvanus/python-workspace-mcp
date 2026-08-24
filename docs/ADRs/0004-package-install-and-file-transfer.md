# ADR 0004: Controlled package installation and workspace file transfer

## Status

Accepted

## Context

Python workspaces should remain offline for ordinary execution, while users must be able to use libraries that were not included in the base image and move data/results into and out of the workspace.

## Decision

Treat package installation, file upload and file download as explicit workspace capabilities. Long-lived execution containers remain `network=none`. Package installation is performed by a short-lived installer container using the PyPI simple index and writes to persistent `.python-packages`. Execution adds that directory to `PYTHONPATH`.

Workspace files are the single storage model. `read_file` returns text to the AI; `get_file_url` provides actual file transfer for both text and binary files; `upload_file` provides ingress.

## Consequences

The normal runtime has no arbitrary Internet access. Package installation is still networked during the install operation, so this is a controlled application-level policy rather than a network-level PyPI firewall. A future package proxy can strengthen that boundary without changing the MCP API.
