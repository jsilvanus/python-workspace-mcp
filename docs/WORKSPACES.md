# Workspaces

A workspace is the durable unit visible to the AI and user.

## Phase 1

Phase 1 has exactly one configured workspace. The API nevertheless exposes workspace identity and accepts an optional workspace ID so the contract does not need to be redesigned for Phase 2.

The workspace is stored outside the runtime container and mounted at `/workspace` inside the Docker runtime.

## Lifecycle invariant

```text
workspace data persists
runtime container may be destroyed/recreated
```

This permits Python runtime upgrades and container recreation without losing user data.

## Path safety

All MCP file paths are resolved relative to the workspace root. Paths escaping that root, including through resolved symlinks, must be rejected.

## Future

Phase 2 changes the implementation to multiple workspaces with per-workspace execution containers and resource policies. The workspace ID becomes an active routing key rather than a Phase 1 validation value.
