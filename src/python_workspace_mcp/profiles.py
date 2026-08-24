from __future__ import annotations

import re

from .config import Settings
from .limits import ResourceLimits
from .resource_profiles import ResourceProfile, builtin_profiles, profile_from_dict
from .state import StateStore


class ResourceProfileManager:
    """Persistent administrator-controlled resource profiles."""

    def __init__(self, settings: Settings) -> None:
        self.store = StateStore(settings.state_path)
        self._ensure_defaults()
        self._profiles = self._load()

    def _ensure_defaults(self) -> None:
        state = self.store.load()
        profiles = state.setdefault("resource_profiles", {})
        for profile_id, profile in builtin_profiles().items():
            profiles.setdefault(profile_id, profile.as_dict())
        self.store.save(state)

    def _load(self) -> dict[str, ResourceProfile]:
        state = self.store.load()
        return {profile_id: profile_from_dict(data) for profile_id, data in state["resource_profiles"].items()}

    def refresh(self) -> None:
        self._profiles = self._load()

    def get(self, profile_id: str) -> ResourceProfile:
        try:
            return self._profiles[profile_id]
        except KeyError as exc:
            raise ValueError(f"Unknown resource profile: {profile_id}") from exc

    def all(self) -> list[ResourceProfile]:
        return list(self._profiles.values())

    def create(self, profile_id: str, name: str, defaults: ResourceLimits, maximums: ResourceLimits) -> ResourceProfile:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", profile_id):
            raise ValueError(f"Invalid profile id: {profile_id!r}")
        if profile_id in self._profiles:
            raise ValueError(f"Resource profile already exists: {profile_id}")
        profile = ResourceProfile(profile_id, name, defaults, maximums)
        profile.validate(defaults)
        state = self.store.load()
        state["resource_profiles"][profile_id] = profile.as_dict()
        self.store.save(state)
        self.refresh()
        return self.get(profile_id)

    def delete(self, profile_id: str) -> None:
        if profile_id in builtin_profiles():
            raise ValueError("Cannot delete a built-in resource profile")
        state = self.store.load()
        if profile_id not in state["resource_profiles"]:
            raise ValueError(f"Unknown resource profile: {profile_id}")
        state["resource_profiles"].pop(profile_id)
        self.store.save(state)
        self.refresh()
