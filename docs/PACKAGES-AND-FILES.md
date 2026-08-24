# Packages and file transfer

## Network policy

Long-lived Python execution containers always run with Docker `network=none`. Arbitrary outbound Internet access is not a workspace capability.

Profiles may grant `package_install`. Package installation uses a short-lived installer container with network access and a pinned PyPI index (`https://pypi.org/simple`), then stores packages persistently in `.python-packages` inside the workspace. The execution container exposes that directory through `PYTHONPATH`.

This is a controlled package-install path, not general Internet access. A future package proxy can provide stronger network-level enforcement, caching, auditing and allow/deny policy.

## File transfer

Workspace files are the single source of truth. `read_file` is for giving the AI text contents. `get_file_url` is for transferring the actual file to a client/user and works for binary artifacts such as PDFs, images, spreadsheets and archives too.

`upload_file` accepts base64 content and writes it into the workspace. Uploads are limited to 25 MiB per call.

File download URLs are signed and expire only when the signing secret changes; access is still scoped to the workspace capability. The download endpoint does not expose arbitrary filesystem paths because paths are resolved through the workspace boundary.

## Capabilities

Resource profiles now include:

- `package_install`: whether PyPI package installation is available
- `package_index`: currently `pypi`
- `outbound_network`: always false in the standard execution runtime
- `file_upload`
- `file_download`

Package installation is enabled for the built-in `standard` and `large` profiles, and disabled for `small`.
