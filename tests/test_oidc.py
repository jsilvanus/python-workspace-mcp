"""OAuth + OIDC sign-in (enabled by OIDC_ISSUER) against a fake OpenID Provider."""
from __future__ import annotations

import base64
import hashlib
import importlib
import json
import re
import secrets
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from starlette.testclient import TestClient

from fake_oidc import FakeOidcProvider
from python_workspace_mcp import main
from python_workspace_mcp.cimd import CimdError, is_cimd_client_id, parse_cimd_document
from python_workspace_mcp.config import Settings
from python_workspace_mcp.oidc_config import ConfigError, load_oidc_settings

PUBLIC_URL = "http://localhost:8000"
CLIENT_ID = "https://client.example/oauth/client.json"
REDIRECT_URI = "https://client.example/callback"
JWT_SECRET = base64.b64encode(b"k" * 32).decode()
MANAGED_ENV = [
    "OIDC_ISSUER", "OIDC_CLIENT_ID", "OIDC_CLIENT_SECRET", "OIDC_SCOPES", "OIDC_BUTTON_LABEL", "OIDC_CREATE_USERS",
    "OIDC_TRUST_EMAIL", "JWT_SECRET", "PYTHON_WORKSPACE_REQUIRE_AUTH", "PYTHON_WORKSPACE_API_KEY", "PYTHON_WORKSPACE_WORKSPACES",
]


async def fake_client_metadata(client_id: str) -> dict:
    if client_id != CLIENT_ID:
        raise CimdError("unknown client")
    return {"client_id": CLIENT_ID, "client_name": "Test Client", "redirect_uris": [REDIRECT_URI]}


@pytest.fixture
def idp():
    with FakeOidcProvider() as provider:
        yield provider


@pytest.fixture
def load_app(tmp_path: Path):
    """Reload the server module with a temporary state dir and the given environment."""
    patch = pytest.MonkeyPatch()

    def load(env: dict[str, str]):
        for name in MANAGED_ENV:
            patch.delenv(name, raising=False)
        base = {
            "PYTHON_WORKSPACE_STATE": str(tmp_path / "state.json"),
            "PYTHON_WORKSPACE_FILES_STATE": str(tmp_path / "files.json"),
            "PYTHON_WORKSPACE_EXECUTIONS_STATE": str(tmp_path / "executions.json"),
            "PYTHON_WORKSPACE_OAUTH_STATE": str(tmp_path / "oauth.json"),
            "PYTHON_WORKSPACE_PATH": str(tmp_path / "workspace"),
            "PYTHON_WORKSPACE_PUBLIC_URL": PUBLIC_URL,
        }
        for name, value in {**base, **env}.items():
            patch.setenv(name, value)
        module = importlib.reload(main)
        if module.oauth_server is not None:
            module.oauth_server.fetch_client_metadata = fake_client_metadata
        return module

    yield load
    patch.undo()
    importlib.reload(main)


def oidc_env(idp: FakeOidcProvider, **extra: str) -> dict[str, str]:
    return {"OIDC_ISSUER": idp.issuer, "OIDC_CLIENT_ID": idp.client_id, "OIDC_CLIENT_SECRET": idp.client_secret or "", "JWT_SECRET": JWT_SECRET, **extra}


def pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(48)
    return verifier, base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")


def authorize_params(challenge: str, state: str = "client-state") -> dict[str, str]:
    return {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": state,
        "scope": "mcp",
        "resource": PUBLIC_URL + "/mcp",
    }


def hidden(page: str, name: str) -> str:
    match = re.search(rf'name="{name}" value="([^"]*)"', page)
    assert match, f"no hidden field {name}"
    return match.group(1).replace("&amp;", "&")


def start_sign_in(client: TestClient, challenge: str) -> str:
    """GET /oauth/authorize -> SSO button -> /oidc/login -> provider; returns our callback URL (path + query)."""
    page = client.get("/oauth/authorize", params=authorize_params(challenge))
    assert page.status_code == 200
    login = re.search(r'href="(/oidc/login\?[^"]+)"', page.text).group(1).replace("&amp;", "&")
    to_idp = client.get(login, follow_redirects=False)
    assert to_idp.status_code == 302
    assert "python_workspace_oidc" in to_idp.headers["set-cookie"]
    assert "Path=/oidc" in to_idp.headers["set-cookie"] and "HttpOnly" in to_idp.headers["set-cookie"]
    back = httpx.get(to_idp.headers["location"], follow_redirects=False)
    assert back.status_code == 302
    callback = urlsplit(back.headers["location"])
    assert f"{callback.scheme}://{callback.netloc}" == PUBLIC_URL and callback.path == "/oidc/callback"
    return f"{callback.path}?{callback.query}"


def sign_in_and_consent(client: TestClient, challenge: str):
    callback = start_sign_in(client, challenge)
    return client.get(callback, follow_redirects=False)


def approve(client: TestClient, consent_page: str, action: str = "approve"):
    response = client.post("/oauth/authorize", data={"oauth": hidden(consent_page, "oauth"), "ticket": hidden(consent_page, "ticket"), "action": action}, follow_redirects=False)
    assert response.status_code == 302
    return urlsplit(response.headers["location"]), {k: v[0] for k, v in parse_qs(urlsplit(response.headers["location"]).query).items()}


def exchange(client: TestClient, code: str, verifier: str):
    return client.post("/oauth/token", data={"grant_type": "authorization_code", "code": code, "client_id": CLIENT_ID, "redirect_uri": REDIRECT_URI, "code_verifier": verifier, "resource": PUBLIC_URL + "/mcp"})


def full_flow(client: TestClient) -> dict:
    verifier, challenge = pkce()
    consent = sign_in_and_consent(client, challenge)
    assert consent.status_code == 200, consent.text
    _, query = approve(client, consent.text)
    token = exchange(client, query["code"], verifier)
    assert token.status_code == 200, token.text
    return token.json()


def mcp_call(client: TestClient, token: str | None, tool: str = "get_user"):
    headers = {"accept": "application/json, text/event-stream", "content-type": "application/json", "mcp-protocol-version": "2025-06-18"}
    if token:
        headers["authorization"] = f"Bearer {token}"
    body = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": tool, "arguments": {}}}
    return client.post("/mcp", headers=headers, content=json.dumps(body))


def tool_result(response) -> dict:
    assert response.status_code == 200, response.text
    result = response.json()["result"]
    assert not result.get("isError"), result
    return result.get("structuredContent") or json.loads(result["content"][0]["text"])


def client_for(module) -> TestClient:
    return TestClient(module.app, base_url=PUBLIC_URL)


# --- OIDC off -------------------------------------------------------------------------------


def test_oidc_off_keeps_todays_behaviour(load_app) -> None:
    module = load_app({})
    assert module.settings.oidc is None and module.oauth_server is None
    assert module.settings.require_auth is False
    module.users.create_user(module.settings.user_id, "Default")
    with client_for(module) as client:
        for path in ("/oidc/login", "/oidc/callback", "/oauth/authorize", "/.well-known/oauth-authorization-server", "/.well-known/oauth-protected-resource/mcp", "/.well-known/openid-configuration"):
            assert client.get(path).status_code == 404, path
        assert client.post("/oauth/token").status_code == 404
        assert tool_result(mcp_call(client, None))["id"] == module.settings.user_id
        rejected = mcp_call(client, "not-a-key")
        assert rejected.status_code == 401 and rejected.headers["www-authenticate"] == "Bearer"


def test_oidc_off_with_require_auth_and_api_key(load_app) -> None:
    module = load_app({"PYTHON_WORKSPACE_REQUIRE_AUTH": "true"})
    module.users.create_user("alice", "Alice")
    key = module.users.create_api_key("alice")
    with client_for(module) as client:
        response = mcp_call(client, None)
        assert response.status_code == 401 and response.headers["www-authenticate"] == "Bearer"
        assert tool_result(mcp_call(client, key))["id"] == "alice"


# --- configuration --------------------------------------------------------------------------


def test_config_errors() -> None:
    good = {"OIDC_ISSUER": "https://auth.example.org/application/o/pwm/", "OIDC_CLIENT_ID": "pwm", "JWT_SECRET": JWT_SECRET}
    assert load_oidc_settings({}, PUBLIC_URL) is None
    assert load_oidc_settings({"OIDC_ISSUER": " "}, PUBLIC_URL) is None
    settings = load_oidc_settings(good, "https://pwm.example.org")
    assert settings.scopes == "openid email profile" and settings.button_label == "Sign in with single sign-on"
    assert settings.client_secret is None and not settings.create_users and not settings.trust_email and settings.production
    cases = [
        ({"OIDC_CLIENT_ID": ""}, "OIDC_CLIENT_ID"),
        ({"OIDC_ISSUER": "auth.example.org"}, "absolute"),
        ({"OIDC_SCOPES": "email profile"}, "openid"),
        ({"OIDC_CREATE_USERS": "maybe"}, "OIDC_CREATE_USERS"),
        ({"OIDC_TRUST_EMAIL": "2"}, "OIDC_TRUST_EMAIL"),
        ({"JWT_SECRET": ""}, "JWT_SECRET"),
        ({"JWT_SECRET": base64.b64encode(b"short").decode()}, "32 bytes"),
        ({"JWT_SECRET": "not base64!"}, "base64"),
    ]
    for override, message in cases:
        with pytest.raises(ConfigError, match=message):
            load_oidc_settings({**good, **override}, PUBLIC_URL)
    with pytest.raises(ConfigError, match="https"):
        load_oidc_settings({**good, "OIDC_ISSUER": "http://auth.example.org/"}, "https://pwm.example.org")
    assert load_oidc_settings({**good, "OIDC_ISSUER": "http://127.0.0.1:9000/"}, PUBLIC_URL).production is False


def test_settings_require_auth_defaults_on_with_oidc(monkeypatch) -> None:
    for name in MANAGED_ENV:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("OIDC_ISSUER", "https://auth.example.org/application/o/pwm/")
    monkeypatch.setenv("OIDC_CLIENT_ID", "pwm")
    monkeypatch.setenv("JWT_SECRET", JWT_SECRET)
    assert Settings.from_env().require_auth is True
    monkeypatch.setenv("PYTHON_WORKSPACE_REQUIRE_AUTH", "false")
    assert Settings.from_env().require_auth is False
    monkeypatch.setenv("PYTHON_WORKSPACE_REQUIRE_AUTH", "sometimes")
    with pytest.raises(ConfigError):
        Settings.from_env()
    monkeypatch.delenv("JWT_SECRET")
    monkeypatch.delenv("PYTHON_WORKSPACE_REQUIRE_AUTH")
    with pytest.raises(ConfigError, match="JWT_SECRET"):
        Settings.from_env()


def test_cimd_client_id_rules() -> None:
    assert is_cimd_client_id(CLIENT_ID)
    for bad in ("http://client.example/c.json", "https://client.example/", "https://u:p@client.example/c.json", "https://client.example/c.json?x=1", "https://client.example/a/../c.json", "cimd"):
        assert not is_cimd_client_id(bad), bad
    doc = json.dumps({"client_id": CLIENT_ID, "client_name": "X", "redirect_uris": [REDIRECT_URI]}).encode()
    assert parse_cimd_document(CLIENT_ID, doc)["redirect_uris"] == [REDIRECT_URI]
    with pytest.raises(CimdError):
        parse_cimd_document("https://other.example/c.json", doc)


# --- metadata and resource server -----------------------------------------------------------


def test_metadata_and_401_challenge(load_app, idp) -> None:
    module = load_app(oidc_env(idp))
    with client_for(module) as client:
        resource = client.get("/.well-known/oauth-protected-resource/mcp").json()
        assert resource == client.get("/.well-known/oauth-protected-resource").json()
        assert resource["resource"] == PUBLIC_URL + "/mcp" and resource["authorization_servers"] == [PUBLIC_URL]
        server = client.get("/.well-known/oauth-authorization-server").json()
        assert server == client.get("/.well-known/openid-configuration").json()
        assert server["issuer"] == PUBLIC_URL and server["token_endpoint_auth_methods_supported"] == ["none"]
        assert server["code_challenge_methods_supported"] == ["S256"] and server["client_id_metadata_document_supported"] is True
        for field in ("jwks_uri", "id_token_signing_alg_values_supported", "userinfo_endpoint"):
            assert field not in server

        missing = mcp_call(client, None)
        assert missing.status_code == 401
        assert missing.headers["www-authenticate"] == f'Bearer resource_metadata="{PUBLIC_URL}/.well-known/oauth-protected-resource/mcp", scope="mcp"'
        invalid = mcp_call(client, "garbage")
        assert invalid.status_code == 401 and 'error="invalid_token"' in invalid.headers["www-authenticate"]
        foreign = module.oauth_server.issue_access_token("alice", CLIENT_ID, "mcp")
        module.oauth_server.resource = "https://elsewhere.example/mcp"  # a token for another resource is refused
        other = module.oauth_server.issue_access_token("alice", CLIENT_ID, "mcp")
        module.oauth_server.resource = PUBLIC_URL + "/mcp"
        module.users.create_user("alice", "Alice")
        assert mcp_call(client, other).status_code == 401
        assert tool_result(mcp_call(client, foreign))["id"] == "alice"


def test_api_keys_keep_working_with_oidc(load_app, idp) -> None:
    module = load_app(oidc_env(idp, PYTHON_WORKSPACE_API_KEY="static-key"))
    module.users.create_user(module.settings.user_id, "Service")
    module.users.create_user("bob", "Bob")
    key = module.users.create_api_key("bob")
    with client_for(module) as client:
        assert tool_result(mcp_call(client, key))["id"] == "bob"
        assert tool_result(mcp_call(client, "static-key"))["id"] == module.settings.user_id
        assert client.get("/healthz").status_code == 200


# --- full flows -----------------------------------------------------------------------------


def test_full_mcp_oauth_flow_via_oidc(load_app, idp) -> None:
    module = load_app(oidc_env(idp))
    module.users.create_user("alice", "Alice", email="Alice@Example.org")
    with client_for(module) as client:
        verifier, challenge = pkce()
        page = client.get("/oauth/authorize", params=authorize_params(challenge))
        assert "Sign in with single sign-on" in page.text and "Test Client" in page.text
        assert "password" not in page.text.lower()
        consent = sign_in_and_consent(client, challenge)
        assert consent.status_code == 200
        assert "Test Client" in consent.text and "Alice" in consent.text
        assert "form-action 'self' https://client.example" in consent.headers["content-security-policy"]
        assert consent.headers["cache-control"] == "no-store"
        assert "python_workspace_oidc=" in consent.headers["set-cookie"] and "Max-Age=0" in consent.headers["set-cookie"]

        target, query = approve(client, consent.text)
        assert f"{target.scheme}://{target.netloc}{target.path}" == REDIRECT_URI
        assert query["state"] == "client-state" and query["iss"] == PUBLIC_URL
        token = exchange(client, query["code"], verifier)
        assert token.status_code == 200 and token.headers["cache-control"] == "no-store"
        tokens = token.json()
        assert tokens["token_type"] == "Bearer" and tokens["scope"] == "mcp"
        assert tool_result(mcp_call(client, tokens["access_token"]))["id"] == "alice"
        # The access token is scoped to the user: workspaces list only Alice's (none).
        assert tool_result(mcp_call(client, tokens["access_token"], "get_workspaces"))["workspaces"] == []

        # Codes are single use.
        assert exchange(client, query["code"], verifier).json() == {"error": "invalid_grant"}
        refreshed = client.post("/oauth/token", data={"grant_type": "refresh_token", "refresh_token": tokens["refresh_token"], "client_id": CLIENT_ID})
        assert refreshed.status_code == 200
        assert tool_result(mcp_call(client, refreshed.json()["access_token"]))["id"] == "alice"
    # The identity was linked by verified email; the next sign-in finds it by (issuer, sub).
    links = module.users.oidc_identities("alice")
    assert [(link["issuer"], link["subject"]) for link in links] == [(idp.issuer, "user-1")]


def test_wrong_verifier_and_deny(load_app, idp) -> None:
    module = load_app(oidc_env(idp))
    module.users.create_user("alice", "Alice", email="alice@example.org")
    with client_for(module) as client:
        verifier, challenge = pkce()
        consent = sign_in_and_consent(client, challenge)
        _, query = approve(client, consent.text)
        assert exchange(client, query["code"], "wrong-verifier").json() == {"error": "invalid_grant"}

        _, challenge = pkce()
        consent = sign_in_and_consent(client, challenge)
        _, query = approve(client, consent.text, action="deny")
        assert query["error"] == "access_denied" and "code" not in query and query["state"] == "client-state"


def test_consent_requires_ticket_for_this_request(load_app, idp) -> None:
    module = load_app(oidc_env(idp))
    module.users.create_user("alice", "Alice", email="alice@example.org")
    with client_for(module) as client:
        _, challenge = pkce()
        consent = sign_in_and_consent(client, challenge).text
        no_ticket = client.post("/oauth/authorize", data={"oauth": hidden(consent, "oauth"), "action": "approve"}, follow_redirects=False)
        assert no_ticket.status_code == 401 and "single sign-on" in no_ticket.text
        _, other_challenge = pkce()
        other_oauth = hidden(client.get("/oauth/authorize", params=authorize_params(other_challenge)).text.replace("/oidc/login?oauth=", 'name="oauth" value="'), "oauth")
        stolen = client.post("/oauth/authorize", data={"oauth": other_oauth, "ticket": hidden(consent, "ticket"), "action": "approve"}, follow_redirects=False)
        assert stolen.status_code == 401


def test_invalid_authorization_requests(load_app, idp) -> None:
    module = load_app(oidc_env(idp))
    with client_for(module) as client:
        _, challenge = pkce()
        for override in ({"client_id": "https://unknown.example/c.json"}, {"redirect_uri": "https://evil.example/cb"}, {"code_challenge_method": "plain"}, {"resource": "https://elsewhere.example/mcp"}):
            assert client.get("/oauth/authorize", params={**authorize_params(challenge), **override}).status_code == 400
        assert client.get("/oidc/login").status_code == 400
        assert client.get("/oidc/login", params={"oauth": "bm9wZQ"}).status_code == 400
        assert client.post("/oauth/token", data={"grant_type": "password"}).json() == {"error": "unsupported_grant_type"}


# --- callback protections -------------------------------------------------------------------


def test_callback_state_must_match_cookie(load_app, idp) -> None:
    module = load_app(oidc_env(idp))
    module.users.create_user("alice", "Alice", email="alice@example.org")
    with client_for(module) as client:
        _, challenge = pkce()
        callback = start_sign_in(client, challenge)
        client.cookies.clear()
        refused = client.get(callback)
        assert refused.status_code == 400 and "does not belong to this browser session" in refused.text
        assert client.get(callback, headers={"cookie": "python_workspace_oidc=other-state"}).status_code == 400
        assert idp.token_requests == 0


def test_replayed_state_is_refused(load_app, idp) -> None:
    module = load_app(oidc_env(idp))
    module.users.create_user("alice", "Alice", email="alice@example.org")
    with client_for(module) as client:
        _, challenge = pkce()
        callback = start_sign_in(client, challenge)
        state = parse_qs(urlsplit(callback).query)["state"][0]
        assert client.get(callback).status_code == 200
        assert not client.cookies  # the callback cleared the sign-in cookie
        replay = client.get(callback, headers={"cookie": f"python_workspace_oidc={state}"})
        assert replay.status_code == 400 and "already used" in replay.text


def test_provider_error_and_bad_id_token(load_app, idp) -> None:
    module = load_app(oidc_env(idp))
    module.users.create_user("alice", "Alice", email="alice@example.org")
    with client_for(module) as client:
        idp.authorize_error = "access_denied"
        _, challenge = pkce()
        page = client.get(start_sign_in(client, challenge))
        assert page.status_code == 400 and "did not complete" in page.text and "Try again" in page.text
        idp.authorize_error = None
        idp.id_token_overrides = {"aud": "someone-else"}
        page = client.get(start_sign_in(client, challenge))
        assert page.status_code == 502 and "could not be verified" in page.text
        assert "eyJ" not in page.text  # no token contents in error pages
        idp.id_token_overrides = {"nonce": "forged"}
        assert client.get(start_sign_in(client, challenge)).status_code == 502


# --- identity mapping -----------------------------------------------------------------------


def test_unverified_email_is_not_linked_unless_trusted(load_app, idp) -> None:
    idp.user = {"sub": "user-2", "email": "alice@example.org", "email_verified": False, "name": "Mallory"}
    module = load_app(oidc_env(idp))
    module.users.create_user("alice", "Alice", email="alice@example.org")
    with client_for(module) as client:
        _, challenge = pkce()
        refused = sign_in_and_consent(client, challenge)
        assert refused.status_code == 403 and "No account for this sign-in" in refused.text
    assert module.users.oidc_identities() == []

    module = load_app(oidc_env(idp, OIDC_TRUST_EMAIL="true"))
    with client_for(module) as client:
        assert tool_result(mcp_call(client, full_flow(client)["access_token"]))["id"] == "alice"


def test_email_from_userinfo_when_id_token_lacks_it(load_app, idp) -> None:
    idp.email_in_id_token = False
    module = load_app(oidc_env(idp))
    module.users.create_user("alice", "Alice", email="alice@example.org")
    with client_for(module) as client:
        assert tool_result(mcp_call(client, full_flow(client)["access_token"]))["id"] == "alice"


def test_create_users_off_and_on(load_app, idp) -> None:
    idp.user = {"sub": "newcomer", "email": "new@example.org", "email_verified": False, "preferred_username": "newbie"}
    module = load_app(oidc_env(idp))
    with client_for(module) as client:
        _, challenge = pkce()
        assert sign_in_and_consent(client, challenge).status_code == 403
    assert module.users.all() == []

    module = load_app(oidc_env(idp, OIDC_CREATE_USERS="true"))
    with client_for(module) as client:
        user = tool_result(mcp_call(client, full_flow(client)["access_token"]))
        assert user["id"].startswith("oidc-") and user["name"] == "newbie"
        # Signing in again reuses the same account.
        assert tool_result(mcp_call(client, full_flow(client)["access_token"]))["id"] == user["id"]
    created = module.users.get(user["id"])
    assert created.email is None  # unverified email is not stored
    assert len(module.users.all()) == 1


def test_deleted_user_loses_oauth_access(load_app, idp) -> None:
    module = load_app(oidc_env(idp))
    module.users.create_user("alice", "Alice", email="alice@example.org")
    with client_for(module) as client:
        tokens = full_flow(client)
        module.users.delete_user("alice")
        assert module.users.oidc_identities() == []
        response = mcp_call(client, tokens["access_token"])
        assert response.status_code == 401 and 'error="invalid_token"' in response.headers["www-authenticate"]
        refreshed = client.post("/oauth/token", data={"grant_type": "refresh_token", "refresh_token": tokens["refresh_token"], "client_id": CLIENT_ID})
        assert refreshed.json() == {"error": "invalid_grant"}
        _, challenge = pkce()
        # The link is gone and the email no longer matches anyone: no account.
        assert sign_in_and_consent(client, challenge).status_code == 403


def test_public_client_without_secret(load_app) -> None:
    with FakeOidcProvider(client_secret=None) as provider:
        module = load_app(oidc_env(provider))
        assert module.settings.oidc.client_secret is None
        module.users.create_user("alice", "Alice", email="alice@example.org")
        with client_for(module) as client:
            assert tool_result(mcp_call(client, full_flow(client)["access_token"]))["id"] == "alice"


def test_oidc_login_is_rate_limited(load_app, idp) -> None:
    module = load_app(oidc_env(idp))
    module.oauth_server.rate_limiter.limit = 2
    with client_for(module) as client:
        codes = [client.get("/oidc/login").status_code for _ in range(3)]
    assert codes == [400, 400, 429]
