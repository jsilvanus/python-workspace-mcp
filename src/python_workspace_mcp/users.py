from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .state import StateStore

if TYPE_CHECKING:
    from .config import Settings


@dataclass(frozen=True)
class User:
    id: str
    name: str


@dataclass(frozen=True)
class Principal:
    user: User
    auth_method: str


class UserManager:
    """Persistent user and API-key registry for the self-hosted deployment."""

    def __init__(self, store: StateStore, settings: Settings) -> None:
        self.store = store
        self.settings = settings

    @classmethod
    def from_settings(cls, settings: Settings) -> "UserManager":
        return cls(StateStore(settings.state_path), settings)

    def all(self) -> list[User]:
        return [User(id=user_id, name=data["name"]) for user_id, data in self.store.load()["users"].items()]

    def get(self, user_id: str | None = None) -> User:
        user_id = user_id or self.settings.user_id
        data = self.store.load()["users"].get(user_id)
        if data is None:
            raise ValueError(f"Unknown user: {user_id}")
        return User(id=user_id, name=data["name"])

    def current(self) -> User:
        return self.get(self.settings.user_id)

    def info(self, user_id: str | None = None) -> dict:
        user = self.get(user_id)
        return {"id": user.id, "name": user.name}

    def create_user(self, user_id: str, name: str) -> User:
        state = self.store.load()
        if user_id in state["users"]:
            raise ValueError(f"User already exists: {user_id}")
        state["users"][user_id] = {"name": name}
        self.store.save(state)
        return User(user_id, name)

    def delete_user(self, user_id: str) -> None:
        if user_id == self.settings.user_id:
            raise ValueError("Cannot delete the configured service user")
        state = self.store.load()
        if user_id not in state["users"]:
            raise ValueError(f"Unknown user: {user_id}")
        owned = [w for w, data in state["workspaces"].items() if data.get("owner_user_id") == user_id]
        if owned:
            raise ValueError(f"User owns workspaces: {', '.join(owned)}")
        state["users"].pop(user_id)
        for key, data in list(state["api_keys"].items()):
            if data.get("user_id") == user_id:
                state["api_keys"].pop(key)
        self.store.save(state)

    def create_api_key(self, user_id: str, label: str = "") -> str:
        self.get(user_id)
        raw = "pwm_" + secrets.token_urlsafe(32)
        digest = hashlib.sha256(raw.encode()).hexdigest()
        state = self.store.load()
        state["api_keys"][digest] = {"user_id": user_id, "label": label}
        self.store.save(state)
        return raw

    def revoke_api_key(self, raw_key: str) -> None:
        digest = hashlib.sha256(raw_key.encode()).hexdigest()
        state = self.store.load()
        if digest not in state["api_keys"]:
            raise ValueError("Unknown API key")
        state["api_keys"].pop(digest)
        self.store.save(state)

    def resolve_api_key(self, raw_key: str) -> Principal:
        digest = hashlib.sha256(raw_key.encode()).hexdigest()
        data = self.store.load()["api_keys"].get(digest)
        if data is None:
            raise ValueError("Invalid API key")
        return Principal(self.get(data["user_id"]), "api-key")

    def principal(self, auth_method: str = "local") -> Principal:
        return Principal(user=self.current(), auth_method=auth_method)
