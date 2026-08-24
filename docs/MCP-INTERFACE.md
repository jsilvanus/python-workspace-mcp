# MCP Interface

The MCP interface is the stable application contract. Deployment profiles may change execution infrastructure without changing the conceptual tool surface.

## Transport

Phase 1 uses **Streamable HTTP** at `/mcp`. Stdio is not a primary deployment transport.

## API version

The application contract reports `api_version: "1"` through `get_system_info`. Software release version and deployment profile are separate concepts.

## Tools

### `get_workspaces`
Lists workspaces visible to the caller. Phase 1 returns exactly one workspace and a `default_workspace_id`.

### `get_workspace`
Returns workspace metadata. `workspace_id` is optional in Phase 1 because only one workspace exists.

### `get_system_info`
Returns server/API version, deployment profile, transport, runtime information, capabilities and known limits. This is the discovery/help surface for an agent connecting to an unfamiliar deployment.

### `execute_python`
Executes Python in the selected workspace.

Inputs:
- `code`: Python source code.
- `workspace_id`: optional workspace identifier.

Returns:
- `execution_id`;
- success/failure;
- exit code;
- stdout;
- stderr;
- duration;
- timeout status;
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

Tool arguments already accept an optional `workspace_id` where workspace context matters. Phase 1 validates it against the sole configured workspace. This deliberately avoids baking the assumption of one workspace into the MCP contract.

## Stability rule

Adding optional metadata, capabilities or deployment-specific limits is preferred to breaking existing tool semantics. A breaking application contract requires an explicit API-version decision.
