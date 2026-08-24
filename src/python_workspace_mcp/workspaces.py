from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from .config import Settings
from .limits import ResourceLimits
from .profiles import ResourceProfileManager
from .state import StateStore
from .workspace import Workspace


@dataclass(frozen=True)
class WorkspaceDefinition:
    id: str
    name: str
    root: Path
    limits: ResourceLimits
    maximum_limits: ResourceLimits
    profile_id: str
    owner_user_id: str


class WorkspaceManager:
    """Persistent workspace registry with ownership and resource policies."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.store = StateStore(settings.state_path)
        self.profiles = ResourceProfileManager(settings)
        self._ensure_defaults()
        self._definitions = self._load_definitions()

    def _ensure_defaults(self) -> None:
        state = self.store.load()
        if not state["workspaces"]:
            state["workspaces"][self.settings.default_workspace_id] = {
                "name": self.settings.workspace_name,
                "root": str(self.settings.workspace_path),
                "owner_user_id": self.settings.user_id,
                "profile_id": self.settings.default_resource_profile,
            }
        for item in self.settings.workspace_definitions.split(","):
            item = item.strip()
            if not item:
                continue
            parts = item.split(":", 4)
            if len(parts) not in (3, 4, 5):
                raise ValueError("PYTHON_WORKSPACE_WORKSPACES entries must be id:name:path[:owner_user_id[:profile_id]]")
            workspace_id, name, root = parts[:3]
            owner_user_id = parts[3] if len(parts) >= 4 else self.settings.user_id
            profile_id = parts[4] if len(parts) == 5 else self.settings.default_resource_profile
            self.profiles.get(profile_id)
            state["workspaces"].setdefault(workspace_id, {
                "name": name,
                "root": str(Path(root).expanduser().resolve()),
                "owner_user_id": owner_user_id,
                "profile_id": profile_id,
            })
        self.store.save(state)

    def _load_definitions(self) -> dict[str, WorkspaceDefinition]:
        state = self.store.load()
        definitions: dict[str, WorkspaceDefinition] = {}
        for workspace_id, data in state["workspaces"].items():
            self._validate_id(workspace_id)
            owner = data["owner_user_id"]
            self._validate_id(owner)
            profile_id = data.get("profile_id", self.settings.default_resource_profile)
            profile = self.profiles.get(profile_id)
            definitions[workspace_id] = WorkspaceDefinition(
                id=workspace_id,
                name=data["name"],
                root=Path(data["root"]).expanduser().resolve(),
                limits=profile.defaults,
                maximum_limits=profile.maximums,
                profile_id=profile.id,
                owner_user_id=owner,
            )
        if self.settings.default_workspace_id not in definitions:
            raise ValueError(f"Default workspace is not configured: {self.settings.default_workspace_id}")
        return definitions

    @staticmethod
    def _validate_id(value: str) -> None:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", value):
            raise ValueError(f"Invalid id: {value!r}")

    def refresh(self) -> None:
        self.profiles.refresh()
        self._definitions = self._load_definitions()

    def ids(self) -> list[str]:
        return list(self._definitions)

    def get_definition(self, workspace_id: str | None = None) -> WorkspaceDefinition:
        workspace_id = workspace_id or self.settings.default_workspace_id
        try:
            return self._definitions[workspace_id]
        except KeyError as exc:
            raise ValueError(f"Unknown workspace: {workspace_id}") from exc

    def get(self, workspace_id: str | None = None) -> Workspace:
        definition = self.get_definition(workspace_id)
        definition.root.mkdir(parents=True, exist_ok=True)
        return Workspace(id=definition.id, name=definition.name, root=definition.root)

    def create_workspace(self, workspace_id: str, name: str, root: Path, owner_user_id: str, profile_id: str | None = None) -> WorkspaceDefinition:
        self._validate_id(workspace_id)
        self._validate_id(owner_user_id)
        profile_id = profile_id or self.settings.default_resource_profile
        self.profiles.get(profile_id)
        state = self.store.load()
        if workspace_id in state["workspaces"]:
            raise ValueError(f"Workspace already exists: {workspace_id}")
        state["workspaces"][workspace_id] = {
            "name": name,
            "root": str(root.expanduser().resolve()),
            "owner_user_id": owner_user_id,
            "profile_id": profile_id,
        }
        self.store.save(state)
        self.refresh()
        return self.get_definition(workspace_id)

    def set_profile(self, workspace_id: str, profile_id: str) -> WorkspaceDefinition:
        self.profiles.get(profile_id)
        state = self.store.load()
        if workspace_id not in state["workspaces"]:
            raise ValueError(f"Unknown workspace: {workspace_id}")
        state["workspaces"][workspace_id]["profile_id"] = profile_id
        self.store.save(state)
        self.refresh()
        return self.get_definition(workspace_id)

    def delete_workspace(self, workspace_id: str) -> None:
        if workspace_id == self.settings.default_workspace_id:
            raise ValueError("Cannot delete the default workspace")
        state = self.store.load()
        if workspace_id not in state["workspaces"]:
            raise ValueError(f"Unknown workspace: {workspace_id}")
        state["workspaces"].pop(workspace_id)
        self.store.save(state)
        self.refresh()

    def info(self, workspace_id: str | None = None) -> dict:
        definition = self.get_definition(workspace_id)
        workspace = self.get(definition.id)
        info = workspace.info()
        info["owner_user_id"] = definition.owner_user_id
        info["resource_profile"] = definition.profile_id
        info["limits"] = definition.limits.as_dict()
        info["maximum_limits"] = definition.maximum_limits.as_dict()
        info["runtime"] = {
            "backend": "docker",
            "container": f"{self.settings.docker_container_prefix}-{definition.id}",
        }
        return info

    def all_info(self) -> list[dict]:
        return [self.info(workspace_id) for workspace_id in self.ids()]
