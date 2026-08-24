# MCP Interface

The MCP interface is the stable application contract. Deployment profiles may change execution infrastructure without changing the conceptual tool surface.

## Transport

Phase 1 uses **Streamable HTTP** at `/mcp`. Stdio is not a primary deployment transport.

## API version

The application contract reports `api_version: "1"` through `get_system_info`. Software release version and deployment profile are separate concepts.

## Tools

### `get_workspaces`
Lists workspaces visible to the caller and their effective resource profile/limits.

### `get_workspace`
Returns workspace metadata, including its resource profile, default limits and maximum limits.

### `get_system_info`
Returns server/API version, deployment profile, transport, runtime information, capabilities and known limits. This is the discovery/help surface for an agent connecting to an unfamiliar deployment.

### `execute_python`
Executes Python in the selected workspace.

Inputs:
- `code`: Python source code.
- `workspace_id`: optional workspace identifier.
- `resources`: optional object requesting per-execution resources. Supported fields include `cpu`, `memory_bytes`, `execution_timeout_seconds` (or `timeout`), `pids`, `max_output_bytes` (or `output_bytes`) and `max_artifacts_per_execution` (or `max_artifacts`). Requests are validated against the workspace's resource profile maximums. `storage_bytes` is deliberately a workspace policy and cannot be changed per execution.

If `resources` is omitted, profile defaults are used.

Returns:
- `execution_id`;
- success/failure;
- exit code;
- stdout;
- stderr;
- duration;
- timeout status;
- effective resource limits;
- resource profile;
- detected changed/generated artifacts.

### `list_files`
Lists files/directories under a workspace-relative path.

### `read_file`
Reads a UTF-8 text file from the workspace. Binary files should be retrieved through the artifact/file URL mechanism.

### `delete_file`
Deletes a single workspace file.

### `get_file_url`
Returns an HTTP URL for retrieving a workspace file. Phase 1 uses an HMAC-signed URL; later deployments may use expiring signed/object-storage URLs.

## Workspace selection

Tool arguments already accept an optional `workspace_id` where workspace context matters. Later phases route the request to the authenticated user's owned workspace.

## Resource policy

Resource profiles are administrator-controlled. An MCP caller can request additional resources for an execution, but cannot change the workspace's profile or its maximums. Runtime CPU, memory and PID limits are applied to the Docker workspace runtime; storage remains persistent workspace policy.

## Stability rule

Adding optional metadata, capabilities or deployment-specific limits is preferred to breaking existing tool semantics. A breaking application contract requires an explicit API-version decision. The `resources` argument is optional and therefore preserves existing `execute_python` callers.
