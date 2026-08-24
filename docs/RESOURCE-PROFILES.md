# Resource profiles

Phase 3 uses named administrator-controlled resource profiles to assign execution policies to workspaces.

## Model

Each profile has:

- **defaults**: resources normally applied to executions
- **maximums**: hard ceiling an execution may request

A workspace references exactly one profile. The MCP client may request higher resources for an individual execution, but only up to that workspace profile's maximums.

The AI cannot change a workspace's profile.

```text
administrator
    ↓
resource profile
    ↓
workspace
    ↓
execution request
    ↓
validated effective limits
    ↓
Docker
```

## Built-in profiles

- `small`: 1 CPU / 1 GiB default, up to 2 CPU / 2 GiB
- `standard`: 2 CPU / 4 GiB default, up to 4 CPU / 8 GiB
- `large`: 4 CPU / 16 GiB default, up to 8 CPU / 32 GiB

Storage, timeout, PID, output and artifact ceilings are also profile-controlled.

## CLI

```bash
python-workspace profile list
python-workspace profile show standard
python-workspace profile create researcher "Researcher" --cpu 2 --memory-gb 8 --storage-gb 25 --timeout 600 --max-cpu 4 --max-memory-gb 16 --max-storage-gb 50 --max-timeout 1800
python-workspace profile remove researcher
```

Assign a profile when creating a workspace:

```bash
python-workspace workspace create bob-data "Bob data" ./workspaces/bob bob --profile standard
```

Change it later as an administrator:

```bash
python-workspace workspace set-profile bob-data large
```

## On-demand resources

`execute_python` accepts an optional `resources` object. Omitting it uses profile defaults.

Example:

```json
{
  "code": "run_expensive_analysis()",
  "resources": {
    "cpu": 4,
    "memory_bytes": 6442450944,
    "execution_timeout_seconds": 600
  }
}
```

Every requested value is validated against the workspace profile maximum. Requests above the maximum are rejected. Storage remains a persistent workspace policy; CPU, memory and PID limits are applied to the workspace runtime for the execution. Execution is serialized per workspace while these runtime limits are changed.

This mechanism is deliberately not a billing system. Billing, quotas and richer plan management belong to the hosted/SaaS phase.
