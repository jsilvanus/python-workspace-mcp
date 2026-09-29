from __future__ import annotations

import hashlib
import re
import secrets
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .state import StateStore

if TYPE_CHECKING:
    from .config import Settings


@dataclass(frozen=True)
class User:
    id: str
    name: str
    email: str | None = None


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
        return [self._user(user_id, data) for user_id, data in self.store.load()["users"].items()]

    @staticmethod
    def _user(user_id: str, data: dict) -> User:
        return User(id=user_id, name=data["name"], email=data.get("email") or None)

    def get(self, user_id: str | None = None) -> User:
        user_id = user_id or self.settings.user_id
        data = self.store.load()["users"].get(user_id)
        if data is None:
            raise ValueError(f"Unknown user: {user_id}")
        return self._user(user_id, data)

    def current(self) -> User:
        return self.get(self.settings.user_id)

    def info(self, user_id: str | None = None) -> dict:
        user = self.get(user_id)
        return {"id": user.id, "name": user.name}

    def create_user(self, user_id: str, name: str, email: str | None = None) -> User:
        state = self.store.load()
        if user_id in state["users"]:
            raise ValueError(f"User already exists: {user_id}")
        record: dict = {"name": name}
        email = self._normalize_email(email)
        if email:
            self._ensure_email_free(state, email, user_id)
            record["email"] = email
        state["users"][user_id] = record
        self.store.save(state)
        return User(user_id, name, email)

    def set_email(self, user_id: str, email: str | None) -> User:
        """Set (or clear, with None/empty) the email used to link an OIDC sign-in to this user."""
        state = self.store.load()
        if user_id not in state["users"]:
            raise ValueError(f"Unknown user: {user_id}")
        email = self._normalize_email(email)
        if email:
            self._ensure_email_free(state, email, user_id)
            state["users"][user_id]["email"] = email
        else:
            state["users"][user_id].pop("email", None)
        self.store.save(state)
        return self._user(user_id, state["users"][user_id])

    @staticmethod
    def _normalize_email(email: str | None) -> str | None:
        if email is None or not email.strip():
            return None
        email = email.strip()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+", email):
            raise ValueError(f"Invalid email: {email!r}")
        return email

    @staticmethod
    def _ensure_email_free(state: dict, email: str, user_id: str) -> None:
        for other_id, data in state["users"].items():
            if other_id != user_id and (data.get("email") or "").lower() == email.lower():
                raise ValueError(f"Email already belongs to user {other_id}")

    def find_by_email(self, email: str) -> User | None:
        """Case-insensitive lookup of the user carrying this email."""
        wanted = email.strip().lower()
        for user_id, data in self.store.load()["users"].items():
            if (data.get("email") or "").lower() == wanted:
                return self._user(user_id, data)
        return None

    # --- OIDC identities: (issuer, subject) -> user ---------------------------------

    @staticmethod
    def _identity_key(issuer: str, subject: str) -> str:
        return hashlib.sha256(f"{issuer}\0{subject}".encode()).hexdigest()

    def find_oidc_identity(self, issuer: str, subject: str) -> User | None:
        state = self.store.load()
        data = state["oidc_identities"].get(self._identity_key(issuer, subject))
        if data is None or data.get("issuer") != issuer or data.get("subject") != subject:
            return None
        user = state["users"].get(data["user_id"])
        return None if user is None else self._user(data["user_id"], user)

    def link_oidc_identity(self, issuer: str, subject: str, user_id: str) -> None:
        state = self.store.load()
        if user_id not in state["users"]:
            raise ValueError(f"Unknown user: {user_id}")
        key = self._identity_key(issuer, subject)
        now = int(time.time())
        existing = state["oidc_identities"].get(key)
        state["oidc_identities"][key] = {
            "issuer": issuer,
            "subject": subject,
            "user_id": user_id,
            "created_at": existing["created_at"] if existing else now,
            "last_login_at": now,
        }
        self.store.save(state)

    def oidc_identities(self, user_id: str | None = None) -> list[dict]:
        items = self.store.load()["oidc_identities"].values()
        return [dict(item) for item in items if user_id is None or item.get("user_id") == user_id]

    def unlink_oidc_identities(self, user_id: str) -> int:
        state = self.store.load()
        keys = [key for key, item in state["oidc_identities"].items() if item.get("user_id") == user_id]
        for key in keys:
            state["oidc_identities"].pop(key)
        self.store.save(state)
        return len(keys)

    def create_oidc_user(self, issuer: str, subject: str, name: str, email: str | None) -> User:
        """Create a user for a first OIDC sign-in, with an id derived from (issuer, subject)."""
        user_id = "oidc-" + self._identity_key(issuer, subject)[:16]
        state = self.store.load()
        if email and any((d.get("email") or "").lower() == email.lower() for d in state["users"].values()):
            email = None  # never steal another account's email; the link is by (issuer, subject)
        if user_id not in state["users"]:
            self.create_user(user_id, name[:200] or user_id, email)
        self.link_oidc_identity(issuer, subject, user_id)
        return self.get(user_id)

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
        for key, data in list(state["oidc_identities"].items()):
            if data.get("user_id") == user_id:
                state["oidc_identities"].pop(key)
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
