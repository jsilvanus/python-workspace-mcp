# ADR 0006: Controlled package installation

## Status

Accepted

## Decision

Only profiles with `package_install` enabled may install packages. Installation uses a short-lived Docker container with pip pinned to the PyPI simple index and writes into the workspace's persistent `.python-packages` directory. The long-lived execution container remains `network=none` and uses the persistent directory through `PYTHONPATH`.

Arbitrary outbound network access is not enabled by this capability. A package proxy is a future hardening step if stronger network-level enforcement is required.