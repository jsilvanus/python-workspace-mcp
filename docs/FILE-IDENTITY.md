# File identity and delivery

A workspace owns its files. Containers are runtime implementation details and are never public file identifiers.

The durable hierarchy is:

```text
User -> Workspace -> File
```

A file has an opaque `file_id` derived from its workspace and relative path. The server resolves that ID to a canonical path and verifies that the path remains inside the workspace root.

## Operations

- `list_files(workspace_id)` — metadata for files visible in the workspace.
- `read_file(workspace_id, file_id)` — content for AI inspection when the file is text-like.
- `upload_file(workspace_id, ...)` — copy a file into workspace storage, subject to ownership and storage limits.
- `get_file_url(workspace_id, file_id)` — authenticated/short-lived download URL for transferring the actual file, including binary files.
- `delete_file(workspace_id, file_id)` — remove a workspace file.

`read_file` and download are deliberately distinct: the former exposes content to the model, while the latter transfers the original file to a client.

Container recreation does not change file identity because files live in persistent workspace storage.
