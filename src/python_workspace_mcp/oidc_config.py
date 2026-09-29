"""Environment configuration for OIDC sign-in and the embedded OAuth server.

Everything here is inert unless ``OIDC_ISSUER`` is set: ``load_oidc_settings``
then returns ``None`` and the server behaves exactly as without OAuth.
"""
from __future__ import annotations

import base64
import binascii
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import urlsplit

DEFAULT_SCOPES = "openid email profile"
DEFAULT_BUTTON_LABEL = "Sign in with single sign-on"
_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}


class ConfigError(ValueError):
    """A startup configuration error with a message meant for the operator."""


@dataclass(frozen=True)
class OidcSettings:
    issuer: str
    client_id: str
    client_secret: str | None
    scopes: str
    button_label: str
    create_users: bool
    trust_email: bool
    jwt_secret: bytes
    production: bool

    @property
    def secure_cookies(self) -> bool:
        return self.production


def parse_bool(name: str, value: str | None, default: bool) -> bool:
    if value is None or not value.strip():
        return default
    normalized = value.strip().lower()
    if normalized in _TRUE:
        return True
    if normalized in _FALSE:
        return False
    raise ConfigError(f"{name} must be true or false, got {value!r}")


def is_production(public_base_url: str) -> bool:
    """This repo has no environment switch; a public https:// URL means a real deployment."""
    return urlsplit(public_base_url).scheme == "https"


def load_oidc_settings(env: Mapping[str, str], public_base_url: str) -> OidcSettings | None:
    issuer = (env.get("OIDC_ISSUER") or "").strip()
    if not issuer:
        return None
    production = is_production(public_base_url)
    parts = urlsplit(issuer)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise ConfigError("OIDC_ISSUER must be an absolute http(s) URL")
    if production and parts.scheme != "https":
        raise ConfigError("OIDC_ISSUER must use https:// when PYTHON_WORKSPACE_PUBLIC_URL is https://")
    if parts.query or parts.fragment:
        raise ConfigError("OIDC_ISSUER must not contain a query or fragment")

    client_id = (env.get("OIDC_CLIENT_ID") or "").strip()
    if not client_id:
        raise ConfigError("OIDC_CLIENT_ID is required when OIDC_ISSUER is set")
    client_secret = env.get("OIDC_CLIENT_SECRET") or None

    scopes = " ".join((env.get("OIDC_SCOPES") or DEFAULT_SCOPES).split())
    if "openid" not in scopes.split(" "):
        raise ConfigError("OIDC_SCOPES must contain 'openid'")

    button_label = (env.get("OIDC_BUTTON_LABEL") or "").strip() or DEFAULT_BUTTON_LABEL
    create_users = parse_bool("OIDC_CREATE_USERS", env.get("OIDC_CREATE_USERS"), False)
    trust_email = parse_bool("OIDC_TRUST_EMAIL", env.get("OIDC_TRUST_EMAIL"), False)

    raw_secret = (env.get("JWT_SECRET") or "").strip()
    if not raw_secret:
        raise ConfigError("JWT_SECRET (base64, at least 32 bytes) is required when OIDC_ISSUER is set")
    try:
        jwt_secret = base64.b64decode(raw_secret + "=" * (-len(raw_secret) % 4), altchars=b"-_" if ("-" in raw_secret or "_" in raw_secret) else None, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ConfigError("JWT_SECRET must be base64 encoded") from exc
    if len(jwt_secret) < 32:
        raise ConfigError("JWT_SECRET must decode to at least 32 bytes (e.g. `openssl rand -base64 32`)")

    return OidcSettings(
        issuer=issuer,
        client_id=client_id,
        client_secret=client_secret,
        scopes=scopes,
        button_label=button_label,
        create_users=create_users,
        trust_email=trust_email,
        jwt_secret=jwt_secret,
        production=production,
    )
