from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from .config import Settings
from .limits import ResourceLimits
from .workspace import Workspace


@dataclass(frozen=True)
class WorkspaceDefinition:
    id: str
    name: str
    root: Path
    limits: ResourceLimits


class WorkspaceManager:
    """Phase 2 workspace registry.

    Workspace definitions are currently configuration-backed. This keeps the
    runtime API ready for a database-backed registry in a later phase without
    making the MCP layer depend on storage details.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._definitions = self._load_definitions()

    def _load_definitions(self) -> dict[str, WorkspaceDefinition]:
        definitions: dict[str, WorkspaceDefinition] = {}
        raw = self.settings.workspace_definitions
        for item in raw.split(","):
            item = item.strip()
            if not item:
                continue
            parts = item.split(":", 2)
            if len(parts) != 3:
                raise ValueError("PYTHON_WORKSPACE_WORKSPACES entries must be id:name:path")
            workspace_id, name, root = parts
            self._validate_id(workspace_id)
            definitions[workspace_id] = WorkspaceDefinition(
                id=workspace_id,
                name=name,
                root=Path(root).expanduser().resolve(),
                limits=self._limits_for(workspace_id),
            )
        if not definitions:
            definitions["default"] = WorkspaceDefinition(
                id="default",
                name="Default Workspace",
                root=self.settings.workspace_path,
                limits=self._limits_for("default"),
            )
        return definitions

    def _limits_for(self, workspace_id: str) -> ResourceLimits:
        return ResourceLimits(
            cpu=self.settings.cpu_limit,
            memory_bytes=self.settings.memory_limit_bytes,
            storage_bytes=self.settings.storage_limit_bytes,
            execution_timeout_seconds=self.settings.execution_timeout,
            pids=self.settings.pids_limit,
            max_output_bytes=self.settings.max_output_bytes,
            max_artifacts_per_execution=self.settings.max_artifacts_per_execution,
        )

    @staticmethod
    def _validate_id(workspace_id: str) -> None:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", workspace_id):
            raise ValueError(f"Invalid workspace id: {workspace_id!r}")

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
        return Workspace(
            id=definition.id,
            name=definition.name,
            root=definition.root,
        )

    def info(self, workspace_id: str | None = None) -> dict:
        definition = self.get_definition(workspace_id)
        workspace = self.get(definition.id)
        info = workspace.info()
        info["limits"] = definition.limits.as_dict()
        info["runtime"] = {"backend": "docker"}
        return info

    def all_info(self) -> list[dict]:
        return [self.info(workspace_id) for workspace_id in self.ids()]
