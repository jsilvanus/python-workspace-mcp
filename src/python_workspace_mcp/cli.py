from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import Settings
from .limits import ResourceLimits
from .profiles import ResourceProfileManager
from .users import UserManager
from .workspaces import WorkspaceManager


def _limits_from_args(args: argparse.Namespace, prefix: str = "") -> ResourceLimits:
    return ResourceLimits(
        cpu=getattr(args, f"{prefix}cpu"),
        memory_bytes=getattr(args, f"{prefix}memory_gb") * 1024**3,
        storage_bytes=getattr(args, f"{prefix}storage_gb") * 1024**3,
        execution_timeout_seconds=getattr(args, f"{prefix}timeout"),
        pids=getattr(args, f"{prefix}pids"),
        max_output_bytes=getattr(args, f"{prefix}output_mb") * 1024**2,
        max_artifacts_per_execution=getattr(args, f"{prefix}artifacts"),
    )


def _add_limit_arguments(parser: argparse.ArgumentParser, prefix: str = "", defaults: tuple[float, float, float, int, int, float, int] = (2, 4, 10, 300, 128, 2, 50)) -> None:
    cpu, memory, storage, timeout, pids, output, artifacts = defaults
    parser.add_argument(f"--{prefix}cpu", type=float, default=cpu)
    parser.add_argument(f"--{prefix}memory-gb", type=float, default=memory)
    parser.add_argument(f"--{prefix}storage-gb", type=float, default=storage)
    parser.add_argument(f"--{prefix}timeout", type=int, default=timeout)
    parser.add_argument(f"--{prefix}pids", type=int, default=pids)
    parser.add_argument(f"--{prefix}output-mb", type=float, default=output)
    parser.add_argument(f"--{prefix}artifacts", type=int, default=artifacts)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python-workspace", description="Manage a self-hosted Python Workspace MCP instance.")
    sub = parser.add_subparsers(dest="command", required=True)

    user = sub.add_parser("user", help="Manage users")
    user_sub = user.add_subparsers(dest="action", required=True)
    add = user_sub.add_parser("add", help="Create a user")
    add.add_argument("id")
    add.add_argument("name")
    user_sub.add_parser("list", help="List users")
    remove = user_sub.add_parser("remove", help="Remove a user")
    remove.add_argument("id")

    key = sub.add_parser("key", help="Manage API keys")
    key_sub = key.add_subparsers(dest="action", required=True)
    create = key_sub.add_parser("create", help="Create an API key; print it once")
    create.add_argument("user_id")
    create.add_argument("--label", default="")
    revoke = key_sub.add_parser("revoke", help="Revoke an API key")
    revoke.add_argument("key")

    profile = sub.add_parser("profile", help="Manage resource profiles")
    profile_sub = profile.add_subparsers(dest="action", required=True)
    profile_sub.add_parser("list", help="List resource profiles")
    show = profile_sub.add_parser("show", help="Show a resource profile")
    show.add_argument("id")
    create_profile = profile_sub.add_parser("create", help="Create a resource profile")
    create_profile.add_argument("id")
    create_profile.add_argument("name")
    create_profile.add_argument("--max-cpu", type=float, default=4)
    create_profile.add_argument("--max-memory-gb", type=float, default=8)
    create_profile.add_argument("--max-storage-gb", type=float, default=25)
    create_profile.add_argument("--max-timeout", type=int, default=900)
    create_profile.add_argument("--max-pids", type=int, default=256)
    create_profile.add_argument("--max-output-mb", type=float, default=4)
    create_profile.add_argument("--max-artifacts", type=int, default=100)
    _add_limit_arguments(create_profile, defaults=(2, 4, 10, 300, 128, 2, 50))
    remove_profile = profile_sub.add_parser("remove", help="Remove a custom resource profile")
    remove_profile.add_argument("id")

    mcp_config = sub.add_parser("mcp-config", help="Print client configuration for connecting an MCP client to this server")
    mcp_config.add_argument("--name", default="python-workspace", help="Server name/label to use in generated configs")
    mcp_config.add_argument("--format", dest="output_format", choices=["all", "vscode", "claude-code", "url"], default="all", help="Which config format(s) to print")
    mcp_config.add_argument("--base-url", default=None, help="Override the public base URL (defaults to PYTHON_WORKSPACE_PUBLIC_URL / --public-url setting)")
    mcp_config.add_argument("--api-key", default=None, help="Embed this exact API key as the bearer token instead of creating or looking one up")
    mcp_config.add_argument("--create-key-for", metavar="USER_ID", default=None, help="Create a new API key for this user and embed it in the generated config")
    mcp_config.add_argument("--key-label", default="mcp-client", help="Label to attach when --create-key-for creates a new key")

    workspace = sub.add_parser("workspace", help="Manage workspaces")
    workspace_sub = workspace.add_subparsers(dest="action", required=True)
    workspace_sub.add_parser("list", help="List workspaces")
    create_ws = workspace_sub.add_parser("create", help="Create a workspace")
    create_ws.add_argument("id")
    create_ws.add_argument("name")
    create_ws.add_argument("path", type=Path)
    create_ws.add_argument("owner_user_id")
    create_ws.add_argument("--profile", default=None)
    set_profile = workspace_sub.add_parser("set-profile", help="Change a workspace resource profile")
    set_profile.add_argument("id")
    set_profile.add_argument("profile")
    remove_ws = workspace_sub.add_parser("remove", help="Remove a workspace definition")
    remove_ws.add_argument("id")

    return parser


def _mcp_url(settings: Settings, base_url: str | None) -> str:
    return f"{(base_url or settings.public_base_url).rstrip('/')}/mcp"


def _resolve_api_key(args: argparse.Namespace, settings: Settings, users: UserManager) -> tuple[str | None, str | None]:
    """Return (key, source_note), or (None, None) if no key is available/needed."""
    if args.api_key:
        return args.api_key, "provided via --api-key"
    if args.create_key_for:
        key = users.create_api_key(args.create_key_for, args.key_label)
        return key, f"newly created for user {args.create_key_for!r} (label={args.key_label!r}); store it now, it will not be shown again"
    if settings.api_key:
        return settings.api_key, "the static PYTHON_WORKSPACE_API_KEY configured on the server"
    return None, None


def _print_mcp_config(args: argparse.Namespace, settings: Settings, users: UserManager) -> None:
    url = _mcp_url(settings, args.base_url)
    name = args.name
    key, source = _resolve_api_key(args, settings, users)

    if key:
        print(f"# Using an API key: {source}")
        if source and source.startswith("newly created"):
            print(f"#   {key}")
        print()
    elif settings.require_auth:
        print("# WARNING: this server has PYTHON_WORKSPACE_REQUIRE_AUTH enabled but no API key was")
        print("# resolved. Pass --api-key <key> or --create-key-for <user_id>, or the generated")
        print("# configs below will fail with 401 Unauthorized.")
        print()
    else:
        print("# No API key configured — this server currently accepts unauthenticated requests")
        print("# (PYTHON_WORKSPACE_REQUIRE_AUTH is not set). Fine for local use; set")
        print("# PYTHON_WORKSPACE_API_KEY and PYTHON_WORKSPACE_REQUIRE_AUTH=true before exposing")
        print("# this server beyond localhost, then rerun with --api-key/--create-key-for.")
        print()

    show = lambda fmt: args.output_format in ("all", fmt)

    if show("vscode"):
        print("## VS Code (.vscode/mcp.json)")
        print("```jsonc")
        if key:
            print(json.dumps({
                "servers": {
                    name: {
                        "type": "http",
                        "url": url,
                        "headers": {"Authorization": f"Bearer {key}"},
                    }
                }
            }, indent=2))
        else:
            print(json.dumps({
                "servers": {
                    name: {
                        "type": "http",
                        "url": url,
                    }
                }
            }, indent=2))
        print("```")
        print()

    if show("claude-code"):
        print("## Claude Code CLI")
        print("```bash")
        if key:
            print(f'claude mcp add --transport http {name} {url} --header "Authorization: Bearer {key}"')
        else:
            print(f"claude mcp add --transport http {name} {url}")
        print("```")
        print()
        print("Equivalent `.mcp.json` / `~/.claude.json` entry:")
        print("```json")
        entry: dict = {"type": "http", "url": url}
        if key:
            entry["headers"] = {"Authorization": f"Bearer {key}"}
        print(json.dumps({"mcpServers": {name: entry}}, indent=2))
        print("```")
        print()

    if show("url"):
        print("## Raw endpoint (any Streamable HTTP MCP client)")
        print(f"URL:     {url}")
        if key:
            print("Headers: Authorization: Bearer " + key)
        else:
            print("Headers: (none required)")
        print()
        print("curl smoke test:")
        header_flag = f' -H "Authorization: Bearer {key}"' if key else ""
        print(
            f'curl -sS -X POST {url}{header_flag} '
            '-H "Content-Type: application/json" -H "Accept: application/json, text/event-stream" '
            '-d \'{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"test","version":"1"}}}\''
        )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = Settings.from_env()
    users = UserManager.from_settings(settings)
    workspaces = WorkspaceManager(settings)
    profiles = workspaces.profiles

    if args.command == "user":
        if args.action == "add":
            user = users.create_user(args.id, args.name)
            print(f"created user {user.id}: {user.name}")
        elif args.action == "list":
            for user in users.all():
                print(f"{user.id}\t{user.name}")
        elif args.action == "remove":
            users.delete_user(args.id)
            print(f"removed user {args.id}")
        return 0

    if args.command == "key":
        if args.action == "create":
            key = users.create_api_key(args.user_id, args.label)
            print(key)
            print("Store this key now; it will not be shown again.")
        elif args.action == "revoke":
            users.revoke_api_key(args.key)
            print("revoked API key")
        return 0

    if args.command == "profile":
        if args.action == "list":
            for profile in profiles.all():
                print(f"{profile.id}\t{profile.name}\tdefault={profile.defaults.cpu}cpu/{profile.defaults.memory_bytes // 1024**3}GiB\tmax={profile.maximums.cpu}cpu/{profile.maximums.memory_bytes // 1024**3}GiB")
        elif args.action == "show":
            profile = profiles.get(args.id)
            print(profile.as_dict())
        elif args.action == "create":
            defaults = _limits_from_args(args)
            maximums = ResourceLimits(
                cpu=args.max_cpu,
                memory_bytes=int(args.max_memory_gb * 1024**3),
                storage_bytes=int(args.max_storage_gb * 1024**3),
                execution_timeout_seconds=args.max_timeout,
                pids=args.max_pids,
                max_output_bytes=int(args.max_output_mb * 1024**2),
                max_artifacts_per_execution=args.max_artifacts,
            )
            profile = profiles.create(args.id, args.name, defaults, maximums)
            print(f"created resource profile {profile.id}: {profile.name}")
        elif args.action == "remove":
            profiles.delete(args.id)
            print(f"removed resource profile {args.id}")
        return 0

    if args.command == "mcp-config":
        _print_mcp_config(args, settings, users)
        return 0

    if args.command == "workspace":
        if args.action == "list":
            for info in workspaces.all_info():
                print(f"{info['id']}\t{info['name']}\t{info['owner_user_id']}\t{info['resource_profile']}\t{info['root']}")
        elif args.action == "create":
            definition = workspaces.create_workspace(args.id, args.name, args.path, args.owner_user_id, args.profile)
            print(f"created workspace {definition.id}: {definition.name} (profile={definition.profile_id})")
        elif args.action == "set-profile":
            definition = workspaces.set_profile(args.id, args.profile)
            print(f"updated workspace {definition.id}: profile={definition.profile_id}")
        elif args.action == "remove":
            workspaces.delete_workspace(args.id)
            print(f"removed workspace definition {args.id}")
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
