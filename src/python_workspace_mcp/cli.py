from __future__ import annotations

import argparse
from pathlib import Path

from .config import Settings
from .users import UserManager
from .workspaces import WorkspaceManager


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

    workspace = sub.add_parser("workspace", help="Manage workspaces")
    workspace_sub = workspace.add_subparsers(dest="action", required=True)
    workspace_sub.add_parser("list", help="List workspaces")
    create_ws = workspace_sub.add_parser("create", help="Create a workspace")
    create_ws.add_argument("id")
    create_ws.add_argument("name")
    create_ws.add_argument("path", type=Path)
    create_ws.add_argument("owner_user_id")
    remove_ws = workspace_sub.add_parser("remove", help="Remove a workspace definition")
    remove_ws.add_argument("id")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = Settings.from_env()
    users = UserManager.from_settings(settings)
    workspaces = WorkspaceManager(settings)

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

    if args.command == "workspace":
        if args.action == "list":
            for info in workspaces.all_info():
                print(f"{info['id']}\t{info['name']}\t{info['owner_user_id']}\t{info['root']}")
        elif args.action == "create":
            definition = workspaces.create_workspace(args.id, args.name, args.path, args.owner_user_id)
            print(f"created workspace {definition.id}: {definition.name}")
        elif args.action == "remove":
            workspaces.delete_workspace(args.id)
            print(f"removed workspace definition {args.id}")
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
