"""Embedded OAuth authorization server + resource server for /mcp, with OIDC sign-in.

Mounted only when ``OIDC_ISSUER`` is set. It ports the behaviour of jsilvanus/codestash
``mcp/api-connector-style`` (CIMD client ids, S256 PKCE, single-use authorization codes,
refresh tokens, HS256 access tokens bound to ``iss`` = public URL and ``aud`` = ``<public URL>/mcp``,
RFC 9728 protected-resource metadata, login tickets carrying the signed-in user to the consent step,
CSP ``form-action`` that allows the client's redirect). The only difference is how the user signs in:
there is no password; ``/oauth/authorize`` offers the single sign-on button, which runs the OIDC
Relying Party flow (``/oidc/login`` -> identity provider -> ``/oidc/callback``) and then shows consent.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import html
import logging
import secrets
import threading
import time
from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import jwt as pyjwt
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from .cimd import fetch_cimd_metadata, is_cimd_client_id
from .json_store import JsonStore
from .oidc_client import OidcClient, OidcError
from .oidc_config import OidcSettings
from .users import Principal, User, UserManager

log = logging.getLogger("python_workspace_mcp.oauth")

SCOPE = "mcp"
ACCESS_TOKEN_TTL = 3600
REFRESH_TOKEN_TTL = 30 * 86400
CODE_TTL = 60
LOGIN_TICKET_TTL = 600
PENDING_LOGIN_TTL = 600
COOKIE_NAME = "python_workspace_oidc"
COOKIE_PATH = "/oidc"
OIDC_RATE_LIMIT = 30  # requests per IP per minute on /oidc/*

PUBLIC_PATH_PREFIXES = ("/.well-known/", "/oauth/", "/oidc/")

ClientMetadataFetcher = Callable[[str], Awaitable[dict[str, Any]]]


class InvalidRequest(ValueError):
    pass


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _sha256(value: str) -> str:
    return _b64url(hashlib.sha256(value.encode()).digest())


def random_token(size: int = 32) -> str:
    return secrets.token_urlsafe(size)


def verify_s256(verifier: str, challenge: str) -> bool:
    return hmac.compare_digest(_sha256(verifier), challenge)


def encode_oauth(params: dict[str, str]) -> str:
    return _b64url(urlencode(params).encode())


def decode_oauth(value: str) -> dict[str, str]:
    try:
        raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        return dict(parse_qsl(raw.decode("utf-8"), keep_blank_values=True))
    except (ValueError, UnicodeDecodeError) as exc:
        raise InvalidRequest("Invalid OAuth request") from exc


# --- HTML -------------------------------------------------------------------------------------


def content_security_policy(form_action: list[str] | None = None) -> str:
    """form-action also governs redirects that follow a form submission (see codestash LEARNED.md)."""
    return "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'; form-action " + " ".join(["'self'", *(form_action or [])])


def redirect_source(uri: str) -> str:
    """CSP source for a redirect URI: its origin, or its scheme for custom schemes (e.g. ``cursor:``)."""
    parts = urlsplit(uri)
    if parts.scheme in ("http", "https") and parts.netloc:
        return f"{parts.scheme}://{parts.netloc}"
    return f"{parts.scheme}:"


def _page(title: str, body: str) -> str:
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{html.escape(title)}</title><style>body{{font-family:system-ui,sans-serif;background:#f6f7f9;margin:0;padding:4rem 1rem}}"
        "main{max-width:420px;margin:0 auto;background:#fff;padding:2rem;border-radius:12px;box-shadow:0 8px 30px rgba(0,0,0,.08)}"
        "h1{margin-top:0}button,.button{display:inline-block;margin-top:1rem;padding:.7rem 1.1rem;border:0;border-radius:7px;cursor:pointer;"
        "background:#1f5fbf;color:#fff;text-decoration:none;font:inherit}.secondary{margin-left:.5rem;background:#eee;color:#000}.error{color:#b00020}</style>"
        f"</head><body><main>{body}</main></body></html>"
    )


def _html(content: str, status: int = 200, form_action: list[str] | None = None) -> HTMLResponse:
    return HTMLResponse(content, status_code=status, headers={"Content-Security-Policy": content_security_policy(form_action), "Cache-Control": "no-store"})


def _invalid_request_page() -> HTMLResponse:
    return _html(_page("Invalid request", "<h1>Invalid authorization request</h1>"), 400)


def _error_page(message: str, status: int, retry_url: str | None = None) -> HTMLResponse:
    back = (
        f'<p><a class="button" href="{html.escape(retry_url)}">Try again</a></p>'
        if retry_url
        else "<p>Return to your MCP client and connect again.</p>"
    )
    return _html(_page("Sign-in failed", f'<h1>Sign-in failed</h1><p class="error">{html.escape(message)}</p>{back}'), status)


# --- Storage ----------------------------------------------------------------------------------


class OAuthStore:
    """Durable authorization codes and refresh tokens (keyed by SHA-256, never stored in clear)."""

    def __init__(self, store: JsonStore) -> None:
        self.store = store
        self._lock = threading.RLock()

    def _load(self) -> dict[str, Any]:
        data = self.store.load()
        data.setdefault("codes", {})
        data.setdefault("refresh_tokens", {})
        now = time.time()
        for bucket in ("codes", "refresh_tokens"):
            data[bucket] = {key: value for key, value in data[bucket].items() if value.get("expires", 0) > now}
        return data

    def save_code(self, code: str, record: dict[str, Any]) -> None:
        with self._lock:
            data = self._load()
            data["codes"][_sha256(code)] = record
            self.store.save(data)

    def consume_code(self, code: str) -> dict[str, Any] | None:
        with self._lock:
            data = self._load()
            record = data["codes"].pop(_sha256(code), None)
            self.store.save(data)
            return record

    def save_refresh_token(self, token: str, record: dict[str, Any]) -> None:
        with self._lock:
            data = self._load()
            data["refresh_tokens"][_sha256(token)] = record
            self.store.save(data)

    def get_refresh_token(self, token: str) -> dict[str, Any] | None:
        with self._lock:
            return self._load()["refresh_tokens"].get(_sha256(token))

    def revoke_user(self, user_id: str) -> None:
        with self._lock:
            data = self._load()
            data["refresh_tokens"] = {k: v for k, v in data["refresh_tokens"].items() if v.get("subject") != user_id}
            self.store.save(data)


class PendingLogins:
    """In-memory OIDC login state (PKCE verifier, nonce, OAuth request) keyed by SHA-256(state), single use, 10 min TTL.

    The server is a single process without a database; a restart just means signing in again.
    """

    def __init__(self) -> None:
        self._items: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def put(self, state: str, record: dict[str, Any]) -> None:
        with self._lock:
            self._prune()
            self._items[_sha256(state)] = {**record, "expires": time.time() + PENDING_LOGIN_TTL}

    def take(self, state: str) -> dict[str, Any] | None:
        with self._lock:
            self._prune()
            return self._items.pop(_sha256(state), None)

    def _prune(self) -> None:
        now = time.time()
        for key in [key for key, value in self._items.items() if value["expires"] <= now]:
            self._items.pop(key)


class RateLimiter:
    """Fixed one-minute window per client IP (the repo had no limiter to reuse)."""

    def __init__(self, limit: int, window: float = 60.0) -> None:
        self.limit = limit
        self.window = window
        self._hits: dict[str, tuple[float, int]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.time()
        with self._lock:
            if len(self._hits) > 10_000:
                self._hits = {k: v for k, v in self._hits.items() if now - v[0] < self.window}
            start, count = self._hits.get(key, (now, 0))
            if now - start >= self.window:
                start, count = now, 0
            count += 1
            self._hits[key] = (start, count)
            return count <= self.limit


# --- Server -----------------------------------------------------------------------------------


class OAuthServer:
    def __init__(self, public_url: str, settings: OidcSettings, users: UserManager, store: OAuthStore) -> None:
        self.public_url = public_url.rstrip("/")
        self.issuer = self.public_url
        self.resource = self.public_url + "/mcp"
        self.settings = settings
        self.users = users
        self.store = store
        self.pending = PendingLogins()
        self.rate_limiter = RateLimiter(OIDC_RATE_LIMIT)
        self.oidc = OidcClient(settings, self.public_url + "/oidc/callback")
        self.fetch_client_metadata: ClientMetadataFetcher = fetch_cimd_metadata
        self._ticket_audience = self.issuer + "/oauth/authorize"

    # -- metadata / resource server --

    def www_authenticate(self, error: str | None = None) -> str:
        value = f'Bearer resource_metadata="{self.public_url}/.well-known/oauth-protected-resource/mcp", scope="{SCOPE}"'
        if error:
            value += f', error="{error}", error_description="The access token is missing, expired or invalid."'
        return value

    def authorization_server_metadata(self) -> dict[str, Any]:
        return {
            "issuer": self.issuer,
            "authorization_endpoint": self.issuer + "/oauth/authorize",
            "token_endpoint": self.issuer + "/oauth/token",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "code_challenge_methods_supported": ["S256"],
            "token_endpoint_auth_methods_supported": ["none"],
            "scopes_supported": [SCOPE],
            "client_id_metadata_document_supported": True,
            "authorization_response_iss_parameter_supported": True,
        }

    def protected_resource_metadata(self) -> dict[str, Any]:
        return {"resource": self.resource, "authorization_servers": [self.issuer], "scopes_supported": [SCOPE], "bearer_methods_supported": ["header"]}

    def issue_access_token(self, subject: str, client_id: str, scope: str) -> str:
        now = int(time.time())
        claims = {"iss": self.issuer, "aud": self.resource, "sub": subject, "client_id": client_id, "scope": scope, "iat": now, "exp": now + ACCESS_TOKEN_TTL}
        return pyjwt.encode(claims, self.settings.jwt_secret, algorithm="HS256")

    def principal_for_access_token(self, token: str) -> Principal | None:
        """Verify signature, iss and aud; the token's user must still exist."""
        try:
            claims = pyjwt.decode(token, self.settings.jwt_secret, algorithms=["HS256"], audience=self.resource, issuer=self.issuer, options={"require": ["exp", "iat", "sub", "iss", "aud"]})
        except pyjwt.PyJWTError:
            return None
        try:
            return Principal(self.users.get(claims["sub"]), "oauth")
        except ValueError:
            return None

    # -- authorization request --

    async def validate_request(self, params: dict[str, str]) -> dict[str, Any]:
        if (
            params.get("response_type") != "code"
            or not params.get("client_id")
            or not params.get("redirect_uri")
            or not params.get("code_challenge")
            or params.get("code_challenge_method") != "S256"
        ):
            raise InvalidRequest("Invalid OAuth request")
        if params.get("resource") and params["resource"] != self.resource:
            raise InvalidRequest("Invalid resource")
        if not is_cimd_client_id(params["client_id"]):
            raise InvalidRequest("Invalid client_id")
        try:
            metadata = await self.fetch_client_metadata(params["client_id"])
        except Exception as exc:  # network/document errors all mean "unknown client"
            raise InvalidRequest("Unable to load client metadata") from exc
        if params["redirect_uri"] not in metadata.get("redirect_uris", []):
            raise InvalidRequest("Invalid redirect_uri")
        return metadata

    def _issue_login_ticket(self, user: User, oauth: str) -> str:
        now = int(time.time())
        claims = {"typ": "login", "oauth": _sha256(oauth), "sub": user.id, "iss": self.issuer, "aud": self._ticket_audience, "iat": now, "exp": now + LOGIN_TICKET_TTL}
        return pyjwt.encode(claims, self.settings.jwt_secret, algorithm="HS256")

    def _verify_login_ticket(self, ticket: str, oauth: str) -> User | None:
        try:
            claims = pyjwt.decode(ticket, self.settings.jwt_secret, algorithms=["HS256"], audience=self._ticket_audience, issuer=self.issuer, options={"require": ["exp", "sub"]})
        except pyjwt.PyJWTError:
            return None
        if claims.get("typ") != "login" or not hmac.compare_digest(str(claims.get("oauth", "")), _sha256(oauth)):
            return None
        try:
            return self.users.get(claims["sub"])
        except ValueError:
            return None

    def _consent_page(self, oauth: str, params: dict[str, str], metadata: dict[str, Any], user: User) -> HTMLResponse:
        ticket = self._issue_login_ticket(user, oauth)
        client_name = metadata.get("client_name") or params["client_id"]
        body = (
            f"<h1>Authorize MCP client</h1><p><strong>{html.escape(client_name)}</strong> wants access to your Python workspaces as "
            f"<strong>{html.escape(user.name)}</strong>.</p>"
            '<form method="post" action="/oauth/authorize">'
            f'<input type="hidden" name="oauth" value="{html.escape(oauth)}">'
            f'<input type="hidden" name="ticket" value="{html.escape(ticket)}">'
            '<button type="submit" name="action" value="approve">Approve</button>'
            '<button class="secondary" type="submit" name="action" value="deny">Deny</button></form>'
        )
        # Approve/deny redirect to the client: form-action must allow its redirect_uri, or browsers block the redirect.
        return _html(_page("Authorize MCP client", body), form_action=[redirect_source(params["redirect_uri"])])

    def _sign_in_page(self, oauth: str, metadata: dict[str, Any], params: dict[str, str]) -> HTMLResponse:
        client_name = metadata.get("client_name") or params["client_id"]
        login_url = "/oidc/login?" + urlencode({"oauth": oauth})
        body = (
            f"<h1>Sign in</h1><p>Sign in to authorize <strong>{html.escape(client_name)}</strong> to use your Python workspaces.</p>"
            f'<p><a class="button" href="{html.escape(login_url)}">{html.escape(self.settings.button_label)}</a></p>'
        )
        return _html(_page("MCP sign in", body))

    # -- routes --

    def routes(self) -> list[tuple[str, list[str], Callable[[Request], Awaitable[Response]]]]:
        return [
            ("/.well-known/oauth-protected-resource/mcp", ["GET"], self.protected_resource_endpoint),
            ("/.well-known/oauth-protected-resource", ["GET"], self.protected_resource_endpoint),
            ("/.well-known/oauth-authorization-server", ["GET"], self.authorization_server_endpoint),
            # Interoperability alias only: this server is not an OpenID Provider (no jwks_uri, no ID tokens).
            ("/.well-known/openid-configuration", ["GET"], self.authorization_server_endpoint),
            ("/oauth/authorize", ["GET", "POST"], self.authorize),
            ("/oauth/token", ["POST"], self.token),
            ("/oidc/login", ["GET"], self.oidc_login),
            ("/oidc/callback", ["GET"], self.oidc_callback),
        ]

    async def protected_resource_endpoint(self, request: Request) -> Response:
        return JSONResponse(self.protected_resource_metadata())

    async def authorization_server_endpoint(self, request: Request) -> Response:
        return JSONResponse(self.authorization_server_metadata())

    async def authorize(self, request: Request) -> Response:
        if request.method == "GET":
            params = dict(request.query_params)
            try:
                metadata = await self.validate_request(params)
            except InvalidRequest:
                return _invalid_request_page()
            return self._sign_in_page(encode_oauth(params), metadata, params)

        form = await request.form()
        oauth = form.get("oauth")
        if not isinstance(oauth, str) or not oauth:
            return _invalid_request_page()
        try:
            params = decode_oauth(oauth)
            metadata = await self.validate_request(params)
        except InvalidRequest:
            return _invalid_request_page()

        ticket = form.get("ticket")
        user = self._verify_login_ticket(ticket, oauth) if isinstance(ticket, str) and ticket else None
        if user is None:
            # No password sign-in here: start over with single sign-on.
            page = self._sign_in_page(oauth, metadata, params)
            page.status_code = 401
            return page

        target = urlsplit(params["redirect_uri"])
        query = parse_qsl(target.query, keep_blank_values=True)
        if form.get("action") != "approve":
            query.append(("error", "access_denied"))
        else:
            code = random_token()
            self.store.save_code(code, {
                "client_id": params["client_id"],
                "redirect_uri": params["redirect_uri"],
                "challenge": params["code_challenge"],
                "subject": user.id,
                "scope": params.get("scope") or SCOPE,
                "expires": time.time() + CODE_TTL,
            })
            query.append(("code", code))
        query.append(("iss", self.issuer))
        if params.get("state"):
            query.append(("state", params["state"]))
        return RedirectResponse(urlunsplit(target._replace(query=urlencode(query))), status_code=302)

    async def token(self, request: Request) -> Response:
        form = await request.form()
        body = {key: value for key, value in form.items() if isinstance(value, str)}
        headers = {"Cache-Control": "no-store", "Pragma": "no-cache"}  # RFC 6749 §5.1

        def error(code: str) -> JSONResponse:
            return JSONResponse({"error": code}, status_code=400, headers=headers)

        if body.get("resource") and body["resource"] != self.resource:
            return error("invalid_target")

        if body.get("grant_type") == "authorization_code":
            record = self.store.consume_code(body["code"]) if body.get("code") else None
            if (
                record is None
                or body.get("client_id") != record["client_id"]
                or body.get("redirect_uri") != record["redirect_uri"]
                or not body.get("code_verifier")
                or not verify_s256(body["code_verifier"], record["challenge"])
            ):
                return error("invalid_grant")
            try:
                self.users.get(record["subject"])
            except ValueError:
                return error("invalid_grant")
            access = self.issue_access_token(record["subject"], record["client_id"], record["scope"])
            refresh = random_token()
            self.store.save_refresh_token(refresh, {"client_id": record["client_id"], "subject": record["subject"], "scope": record["scope"], "expires": time.time() + REFRESH_TOKEN_TTL})
            return JSONResponse({"access_token": access, "token_type": "Bearer", "expires_in": ACCESS_TOKEN_TTL, "refresh_token": refresh, "scope": record["scope"]}, headers=headers)

        if body.get("grant_type") == "refresh_token":
            record = self.store.get_refresh_token(body["refresh_token"]) if body.get("refresh_token") else None
            if record is None or body.get("client_id") != record["client_id"]:
                return error("invalid_grant")
            try:
                self.users.get(record["subject"])  # a deleted user keeps no access through old refresh tokens
            except ValueError:
                return error("invalid_grant")
            access = self.issue_access_token(record["subject"], record["client_id"], record["scope"])
            return JSONResponse({"access_token": access, "token_type": "Bearer", "expires_in": ACCESS_TOKEN_TTL, "scope": record["scope"]}, headers=headers)

        return error("unsupported_grant_type")

    # -- OIDC relying party --

    def _client_ip(self, request: Request) -> str:
        return request.client.host if request.client else "unknown"

    async def oidc_login(self, request: Request) -> Response:
        if not self.rate_limiter.allow(self._client_ip(request)):
            return _html(_page("Too many requests", "<h1>Too many sign-in attempts</h1><p>Wait a minute and try again.</p>"), 429)
        oauth = request.query_params.get("oauth")
        if not oauth:
            # This server has no web UI of its own; sign-in always belongs to an MCP client's authorization request.
            return _invalid_request_page()
        try:
            await self.validate_request(decode_oauth(oauth))
        except InvalidRequest:
            return _invalid_request_page()

        state, nonce, verifier = random_token(), random_token(), random_token(48)
        try:
            url = await self.oidc.authorization_url(state, nonce, verifier)
        except OidcError as exc:
            log.error("OIDC sign-in could not start: %s", exc)
            return _error_page("The sign-in service is not reachable right now.", 502, "/oidc/login?" + urlencode({"oauth": oauth}))
        self.pending.put(state, {"verifier": verifier, "nonce": nonce, "purpose": "oauth", "oauth": oauth})
        response = RedirectResponse(url, status_code=302)
        response.set_cookie(COOKIE_NAME, state, max_age=PENDING_LOGIN_TTL, path=COOKIE_PATH, httponly=True, samesite="lax", secure=self.settings.secure_cookies)
        return response

    def _clear_cookie(self, response: Response) -> Response:
        response.delete_cookie(COOKIE_NAME, path=COOKIE_PATH, httponly=True, samesite="lax", secure=self.settings.secure_cookies)
        return response

    async def oidc_callback(self, request: Request) -> Response:
        if not self.rate_limiter.allow(self._client_ip(request)):
            return _html(_page("Too many requests", "<h1>Too many sign-in attempts</h1><p>Wait a minute and try again.</p>"), 429)
        query_state = request.query_params.get("state") or ""
        cookie_state = request.cookies.get(COOKIE_NAME) or ""
        if not query_state or not cookie_state or not hmac.compare_digest(query_state, cookie_state):
            log.warning("OIDC callback refused: state does not match the sign-in cookie")
            return self._clear_cookie(_error_page("This sign-in link does not belong to this browser session.", 400))
        pending = self.pending.take(query_state)
        if pending is None:
            log.warning("OIDC callback refused: unknown, expired or already used state")
            return self._clear_cookie(_error_page("This sign-in has expired or was already used.", 400))
        retry_url = "/oidc/login?" + urlencode({"oauth": pending["oauth"]})

        if request.query_params.get("error"):
            log.warning("OIDC provider returned error=%s", request.query_params.get("error")[:100])
            return self._clear_cookie(_error_page("The identity provider did not complete the sign-in.", 400, retry_url))
        code = request.query_params.get("code")
        if not code:
            return self._clear_cookie(_error_page("The identity provider did not return a sign-in code.", 400, retry_url))
        try:
            claims = await self.oidc.exchange(code, pending["verifier"], pending["nonce"])
        except OidcError as exc:
            log.warning("OIDC sign-in failed: %s", exc)
            return self._clear_cookie(_error_page("The sign-in could not be verified.", 502, retry_url))

        user, message = self.resolve_user(claims)
        if user is None:
            log.warning("OIDC sign-in refused for subject hash %s: %s", _sha256(claims["sub"])[:12], message)
            return self._clear_cookie(_error_page(message, 403))
        log.info("OIDC sign-in for user %s", user.id)

        oauth = pending["oauth"]
        try:
            params = decode_oauth(oauth)
            metadata = await self.validate_request(params)
        except InvalidRequest:
            return self._clear_cookie(_invalid_request_page())
        return self._clear_cookie(self._consent_page(oauth, params, metadata, user))

    def resolve_user(self, claims: dict[str, Any]) -> tuple[User | None, str]:
        """Map (issuer, sub) to a local user: existing link, then trusted email, then OIDC_CREATE_USERS."""
        issuer, subject = self.settings.issuer, claims["sub"]
        user = self.users.find_oidc_identity(issuer, subject)
        if user is not None:
            self.users.link_oidc_identity(issuer, subject, user.id)  # updates last_login_at
            return user, ""
        email = claims.get("email") if isinstance(claims.get("email"), str) and claims.get("email") else None
        trusted_email = email if email and (claims.get("email_verified") is True or self.settings.trust_email) else None
        if trusted_email:
            user = self.users.find_by_email(trusted_email)
            if user is not None:
                self.users.link_oidc_identity(issuer, subject, user.id)
                return user, ""
        if self.settings.create_users:
            name = next((claims[k] for k in ("name", "preferred_username", "email") if isinstance(claims.get(k), str) and claims[k].strip()), subject)
            return self.users.create_oidc_user(issuer, subject, name.strip(), trusted_email), ""
        return None, "No account for this sign-in; ask the administrator."
