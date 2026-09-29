"""A small fake OpenID Provider for tests (authentik-shaped issuer URL, RS256 ID tokens)."""
from __future__ import annotations

import base64
import hashlib
import json
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit

from joserfc import jwt
from joserfc.jwk import RSAKey


class FakeOidcProvider:
    def __init__(self, client_id: str = "python-workspace", client_secret: str | None = "idp-secret") -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.key = RSAKey.generate_key(2048, parameters={"kid": "test-key", "use": "sig", "alg": "RS256"})
        # Claims of the user who "signs in" at the provider next.
        self.user: dict[str, Any] = {"sub": "user-1", "email": "alice@example.org", "email_verified": True, "name": "Alice Example"}
        self.email_in_id_token = True
        self.authorize_error: str | None = None
        self.id_token_overrides: dict[str, Any] = {}
        self.codes: dict[str, dict[str, Any]] = {}
        self.access_tokens: dict[str, dict[str, Any]] = {}
        self.token_requests = 0
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self.base = f"http://127.0.0.1:{self._server.server_address[1]}"
        self.issuer = self.base + "/application/o/test/"
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def __enter__(self) -> "FakeOidcProvider":
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._server.shutdown()
        self._server.server_close()

    def discovery(self) -> dict[str, Any]:
        return {
            "issuer": self.issuer,
            "authorization_endpoint": self.base + "/application/o/authorize/",
            "token_endpoint": self.base + "/application/o/token/",
            "userinfo_endpoint": self.base + "/application/o/userinfo/",
            "jwks_uri": self.issuer + "jwks/",
            "response_types_supported": ["code"],
            "subject_types_supported": ["public"],
            "id_token_signing_alg_values_supported": ["RS256"],
            "code_challenge_methods_supported": ["S256"],
        }

    def _handler(self):
        provider = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args: object) -> None:  # keep test output quiet
                pass

            def _json(self, status: int, value: Any) -> None:
                body = json.dumps(value).encode()
                self.send_response(status)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self) -> None:
                url = urlsplit(self.path)
                query = {k: v[0] for k, v in parse_qs(url.query).items()}
                if url.path == "/application/o/test/.well-known/openid-configuration":
                    return self._json(200, provider.discovery())
                if url.path == "/application/o/test/jwks/":
                    return self._json(200, {"keys": [provider.key.as_dict(private=False)]})
                if url.path == "/application/o/authorize/":
                    return self._authorize(query)
                if url.path == "/application/o/userinfo/":
                    token = (self.headers.get("authorization") or "")[len("Bearer "):]
                    claims = provider.access_tokens.get(token)
                    return self._json(200, claims) if claims else self._json(401, {"error": "invalid_token"})
                self._json(404, {"error": "not found"})

            def _authorize(self, query: dict[str, str]) -> None:
                assert query.get("client_id") == provider.client_id
                assert query.get("response_type") == "code"
                assert "openid" in query.get("scope", "").split()
                redirect = query["redirect_uri"]
                if provider.authorize_error:
                    params = {"error": provider.authorize_error, "state": query.get("state", "")}
                else:
                    code = secrets.token_urlsafe(16)
                    provider.codes[code] = {
                        "redirect_uri": redirect,
                        "challenge": query.get("code_challenge"),
                        "method": query.get("code_challenge_method"),
                        "nonce": query.get("nonce"),
                        "user": dict(provider.user),
                    }
                    params = {"code": code, "state": query.get("state", "")}
                self.send_response(302)
                self.send_header("location", redirect + "?" + urlencode(params))
                self.end_headers()

            def do_POST(self) -> None:
                if urlsplit(self.path).path != "/application/o/token/":
                    return self._json(404, {"error": "not found"})
                provider.token_requests += 1
                length = int(self.headers.get("content-length") or 0)
                form = {k: v[0] for k, v in parse_qs(self.rfile.read(length).decode()).items()}
                if provider.client_secret is not None:
                    expected = "Basic " + base64.b64encode(f"{provider.client_id}:{provider.client_secret}".encode()).decode()
                    if self.headers.get("authorization") != expected:
                        return self._json(401, {"error": "invalid_client"})
                entry = provider.codes.pop(form.get("code", ""), None)
                if entry is None or form.get("grant_type") != "authorization_code" or form.get("redirect_uri") != entry["redirect_uri"]:
                    return self._json(400, {"error": "invalid_grant"})
                verifier = form.get("code_verifier", "")
                challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
                if entry["method"] != "S256" or challenge != entry["challenge"]:
                    return self._json(400, {"error": "invalid_grant", "error_description": "PKCE"})
                user = entry["user"]
                now = int(time.time())
                claims: dict[str, Any] = {"iss": provider.issuer, "aud": provider.client_id, "iat": now, "exp": now + 300, "nonce": entry["nonce"], "sub": user["sub"]}
                if provider.email_in_id_token:
                    claims.update({k: v for k, v in user.items() if k != "sub"})
                else:
                    claims.update({k: v for k, v in user.items() if k not in ("sub", "email", "email_verified")})
                claims.update(provider.id_token_overrides)
                id_token = jwt.encode({"alg": "RS256", "kid": "test-key"}, claims, provider.key)
                access_token = secrets.token_urlsafe(16)
                provider.access_tokens[access_token] = dict(user)
                self._json(200, {"access_token": access_token, "token_type": "Bearer", "expires_in": 300, "id_token": id_token})

        return Handler
