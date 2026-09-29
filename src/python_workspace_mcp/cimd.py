"""Client ID Metadata Documents (CIMD): the OAuth client_id is an https URL of its metadata.

Ported from jsilvanus/codestash ``mcp/api-connector-style`` (``src/oauth/cimd.ts``), including
its SSRF guards: https only, no userinfo/query/fragment, public addresses only, at most three
redirects, a 5 s timeout and a 64 KiB document limit.
"""
from __future__ import annotations

import asyncio
import ipaddress
import json
from typing import Any
from urllib.parse import urljoin, urlsplit

import httpx

MAX_BYTES = 64 * 1024
MAX_REDIRECTS = 3
TIMEOUT_SECONDS = 5.0


class CimdError(ValueError):
    pass


def is_cimd_client_id(client_id: str) -> bool:
    try:
        parts = urlsplit(client_id)
    except ValueError:
        return False
    return (
        parts.scheme == "https"
        and bool(parts.hostname)
        and parts.path not in ("", "/")
        and parts.username is None
        and parts.password is None
        and not parts.query
        and not parts.fragment
        and ".." not in parts.path.split("/")
    )


async def _assert_public_host(hostname: str) -> None:
    loop = asyncio.get_running_loop()
    try:
        infos = await loop.getaddrinfo(hostname, 443)
    except OSError as exc:
        raise CimdError("CIMD host does not resolve") from exc
    addresses = {info[4][0] for info in infos}
    if not addresses:
        raise CimdError("CIMD host does not resolve")
    for address in addresses:
        try:
            ip = ipaddress.ip_address(address.split("%", 1)[0])
        except ValueError as exc:
            raise CimdError("CIMD host resolves to an invalid address") from exc
        if not ip.is_global:
            raise CimdError("CIMD host resolves to a non-public address")


async def fetch_cimd_metadata(client_id: str) -> dict[str, Any]:
    if not is_cimd_client_id(client_id):
        raise CimdError("Invalid CIMD client_id")
    current = client_id
    async with httpx.AsyncClient(follow_redirects=False, timeout=TIMEOUT_SECONDS) as client:
        for attempt in range(MAX_REDIRECTS + 1):
            await _assert_public_host(urlsplit(current).hostname or "")
            async with client.stream("GET", current, headers={"accept": "application/json"}) as response:
                if 300 <= response.status_code < 400:
                    location = response.headers.get("location")
                    if not location or attempt == MAX_REDIRECTS:
                        raise CimdError("Invalid CIMD redirect")
                    current = urljoin(current, location)
                    if not is_cimd_client_id(current):
                        raise CimdError("Invalid CIMD redirect")
                    continue
                if response.status_code != 200:
                    raise CimdError("Unable to fetch CIMD document")
                length = response.headers.get("content-length")
                if length and length.isdigit() and int(length) > MAX_BYTES:
                    raise CimdError("CIMD document is too large")
                body = b""
                async for chunk in response.aiter_bytes():
                    body += chunk
                    if len(body) > MAX_BYTES:
                        raise CimdError("CIMD document is too large")
            return parse_cimd_document(client_id, body)
    raise CimdError("Unable to fetch CIMD document")


def parse_cimd_document(client_id: str, body: bytes) -> dict[str, Any]:
    try:
        value = json.loads(body)
    except (ValueError, UnicodeDecodeError) as exc:
        raise CimdError("Invalid CIMD document") from exc
    if not isinstance(value, dict):
        raise CimdError("Invalid CIMD document")
    redirect_uris = value.get("redirect_uris")
    if (
        value.get("client_id") != client_id
        or not isinstance(value.get("client_name"), str)
        or not isinstance(redirect_uris, list)
        or any(not isinstance(uri, str) for uri in redirect_uris)
    ):
        raise CimdError("Invalid CIMD document")
    metadata: dict[str, Any] = {"client_id": client_id, "client_name": value["client_name"], "redirect_uris": list(redirect_uris)}
    for key in ("grant_types", "response_types"):
        if isinstance(value.get(key), list):
            metadata[key] = [item for item in value[key] if isinstance(item, str)]
    if isinstance(value.get("token_endpoint_auth_method"), str):
        metadata["token_endpoint_auth_method"] = value["token_endpoint_auth_method"]
    return metadata
