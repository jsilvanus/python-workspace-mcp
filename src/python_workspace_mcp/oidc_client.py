"""OIDC Relying Party toward the identity provider (e.g. authentik).

The server only *consumes* ID tokens: it never issues them and exposes no JWKS.
Authlib drives the authorization-code + PKCE exchange; the ID token is verified
with joserfc (Authlib's JOSE implementation) against the provider's JWKS.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx
from authlib.integrations.httpx_client import AsyncOAuth2Client
from joserfc import jwt
from joserfc.errors import JoseError
from joserfc.jwk import KeySet

from .oidc_config import OidcSettings

log = logging.getLogger("python_workspace_mcp.oidc")

ASYMMETRIC_ALGORITHMS = ["RS256", "RS384", "RS512", "PS256", "PS384", "PS512", "ES256", "ES384", "ES512", "EdDSA"]
TIMEOUT_SECONDS = 10.0


class OidcError(Exception):
    """Sign-in failed; the message is safe to log but is not shown to the user verbatim."""


class OidcClient:
    def __init__(self, settings: OidcSettings, redirect_uri: str) -> None:
        self.settings = settings
        self.redirect_uri = redirect_uri
        self._metadata: dict[str, Any] | None = None
        self._jwks: KeySet | None = None

    def _http(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=TIMEOUT_SECONDS, follow_redirects=False)

    async def metadata(self) -> dict[str, Any]:
        """Discovery on first use, cached; a failure is not cached so the next request retries."""
        if self._metadata is not None:
            return self._metadata
        url = self.settings.issuer.rstrip("/") + "/.well-known/openid-configuration"
        try:
            async with self._http() as client:
                response = await client.get(url, headers={"accept": "application/json"})
            response.raise_for_status()
            metadata = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise OidcError(f"OIDC discovery failed: {exc.__class__.__name__}") from exc
        if not isinstance(metadata, dict) or metadata.get("issuer") != self.settings.issuer:
            raise OidcError("OIDC discovery document does not match OIDC_ISSUER")
        for key in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
            if not isinstance(metadata.get(key), str):
                raise OidcError(f"OIDC discovery document lacks {key}")
        self._metadata = metadata
        return metadata

    def _oauth_client(self) -> AsyncOAuth2Client:
        return AsyncOAuth2Client(
            client_id=self.settings.client_id,
            client_secret=self.settings.client_secret,
            token_endpoint_auth_method="client_secret_basic" if self.settings.client_secret else "none",
            redirect_uri=self.redirect_uri,
            scope=self.settings.scopes,
            code_challenge_method="S256",
            timeout=TIMEOUT_SECONDS,
            follow_redirects=False,
        )

    async def authorization_url(self, state: str, nonce: str, code_verifier: str) -> str:
        metadata = await self.metadata()
        async with self._oauth_client() as client:
            url, _ = client.create_authorization_url(metadata["authorization_endpoint"], state=state, code_verifier=code_verifier, nonce=nonce)
        return url

    async def _keys(self, refresh: bool = False) -> KeySet:
        if self._jwks is not None and not refresh:
            return self._jwks
        metadata = await self.metadata()
        try:
            async with self._http() as client:
                response = await client.get(metadata["jwks_uri"], headers={"accept": "application/json"})
            response.raise_for_status()
            self._jwks = KeySet.import_key_set(response.json())
        except (httpx.HTTPError, ValueError, JoseError) as exc:
            raise OidcError(f"Fetching the OIDC JWKS failed: {exc.__class__.__name__}") from exc
        return self._jwks

    def _algorithms(self, metadata: dict[str, Any]) -> list[str]:
        advertised = metadata.get("id_token_signing_alg_values_supported") or ["RS256"]
        allowed = [alg for alg in advertised if alg in ASYMMETRIC_ALGORITHMS]
        return allowed or ["RS256"]

    async def _verify_id_token(self, id_token: str, nonce: str) -> dict[str, Any]:
        metadata = await self.metadata()
        algorithms = self._algorithms(metadata)
        try:
            try:
                token = jwt.decode(id_token, await self._keys(), algorithms=algorithms)
            except (JoseError, ValueError):
                # The provider may have rotated its signing key: refetch the JWKS once.
                token = jwt.decode(id_token, await self._keys(refresh=True), algorithms=algorithms)
            claims = token.claims
            jwt.JWTClaimsRegistry(
                leeway=60,
                iss={"essential": True, "value": self.settings.issuer},
                sub={"essential": True},
                aud={"essential": True, "value": self.settings.client_id},
                exp={"essential": True},
                iat={"essential": True},
                nonce={"essential": True, "value": nonce},
            ).validate(claims)
        except (JoseError, ValueError) as exc:
            raise OidcError(f"ID token rejected: {exc.__class__.__name__}") from exc
        audience = claims.get("aud")
        if isinstance(audience, list) and len(audience) > 1 and claims.get("azp") != self.settings.client_id:
            raise OidcError("ID token rejected: azp does not match the client")
        if not isinstance(claims.get("sub"), str) or not claims["sub"]:
            raise OidcError("ID token rejected: no subject")
        return dict(claims)

    async def exchange(self, code: str, code_verifier: str, nonce: str) -> dict[str, Any]:
        """Run the code grant (PKCE), verify the ID token (iss, aud, exp, nonce) and return its claims.

        Userinfo is consulted when the ID token carries no email.
        """
        metadata = await self.metadata()
        try:
            async with self._oauth_client() as client:
                token = await client.fetch_token(metadata["token_endpoint"], grant_type="authorization_code", code=code, code_verifier=code_verifier)
        except Exception as exc:  # Authlib raises OAuthError, httpx errors, ValueError...
            raise OidcError(f"Token exchange failed: {exc.__class__.__name__}") from exc
        id_token = token.get("id_token")
        if not isinstance(id_token, str):
            raise OidcError("Token response has no ID token")
        claims = await self._verify_id_token(id_token, nonce)
        if "email" not in claims and isinstance(metadata.get("userinfo_endpoint"), str) and token.get("access_token"):
            claims.update(await self._userinfo(metadata["userinfo_endpoint"], token["access_token"], claims["sub"]))
        return claims

    async def _userinfo(self, endpoint: str, access_token: str, subject: str) -> dict[str, Any]:
        try:
            async with self._http() as client:
                response = await client.get(endpoint, headers={"authorization": f"Bearer {access_token}", "accept": "application/json"})
            response.raise_for_status()
            info = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            log.warning("OIDC userinfo request failed: %s", exc.__class__.__name__)
            return {}
        if not isinstance(info, dict) or info.get("sub") != subject:
            log.warning("OIDC userinfo ignored: subject does not match the ID token")
            return {}
        return {key: info[key] for key in ("email", "email_verified", "name", "preferred_username") if key in info}
