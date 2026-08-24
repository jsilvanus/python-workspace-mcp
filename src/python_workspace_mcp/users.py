from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import Settings


@dataclass(frozen=True)
class User:
    """A stable owner identity for workspaces and API credentials."""

    id: str
    name: str


@dataclass(frozen=True)
class Principal:
    """Identity resolved from an authenticated MCP request."""

    user: User
    auth_method: str


class UserManager:
    """Minimal Phase 2 user registry.

    Phase 2 intentionally has one configured user. The domain model is kept
    separate so Phase 3 can add multiple users and account management without
    changing the workspace or MCP contracts.
    """

    def __init__(self, user: User) -> None:
        self._user = user

    @classmethod
    def from_settings(cls, settings: Settings) -> "UserManager":
        return cls(User(id=settings.user_id, name=settings.user_name))

    def get(self, user_id: str | None = None) -> User:
        if user_id is None or user_id == self._user.id:
            return self._user
        raise ValueError(f"Unknown user: {user_id}")

    def current(self) -> User:
        return self._user

    def info(self) -> dict:
        return {"id": self._user.id, "name": self._user.name}

    def principal(self, auth_method: str = "api-key") -> Principal:
        return Principal(user=self._user, auth_method=auth_method)
