# Python Workspace MCP

[![CI](https://github.com/jsilvanus/python-workspace-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/jsilvanus/python-workspace-mcp/actions/workflows/ci.yml)

A persistent Python analysis workspace exposed to AI agents through Model Context Protocol (MCP).

Phase 1 provides a single Docker-backed workspace over **Streamable HTTP**. The MCP API is intentionally workspace-aware from the beginning so later deployment profiles can add multiple workspaces without redesigning the contract.

## Phase 1 status

The Phase 1 code, contract, tests and documentation are being completed on the `phase-1` branch. It is **not yet a hardened sandbox** and still requires real Docker/MCP end-to-end validation before it should be considered complete.

Docker provides process/filesystem separation from the MCP server, but CPU, memory, disk, PID, network and stronger isolation controls are deferred to Phase 2.

## Quick start

Requirements:

- Python 3.11+
- Docker
- an MCP client that supports Streamable HTTP

Create an environment and install the server:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e .
```

Build the Python runtime:

```bash
docker build -t python-workspace-mcp-runtime:0.1 runtime/
```

Create the server's user (the server never creates one on its own — see `docs/USER-MODEL.md`):

```bash
python-workspace user add default "Default User"
```

Start the MCP server:

```bash
python -m python_workspace_mcp.main
```

The MCP endpoint is:

```text
http://localhost:8000/mcp
```

For a non-local deployment, set `PYTHON_WORKSPACE_API_KEY` and connect with `Authorization: Bearer <key>`.

To generate ready-to-paste client configuration (VS Code `mcp.json`, `claude mcp add`/`.mcp.json`, or a plain URL + headers block), run:

```bash
python-workspace mcp-config
```

Add `--create-key-for <user_id>` to mint a fresh API key and embed it, `--api-key <key>` to embed one you already have, `--format {vscode,claude-code,url}` to print just one format, and `--base-url` if the server is reachable at a different address than `PYTHON_WORKSPACE_PUBLIC_URL`.

## MCP surface

- `get_workspaces`
- `get_workspace`
- `get_system_info`
- `execute_python`
- `list_files`
- `read_file`
- `delete_file`
- `get_file_url`

`get_workspaces` returns one workspace in Phase 1. Workspace IDs are already part of the contract where relevant so Phase 2 can activate multiple workspaces without changing the tool model.

## Runtime

The initial runtime includes:

- numpy
- pandas
- scipy
- statsmodels
- sympy
- matplotlib
- seaborn
- openpyxl

The package set is defined in `runtime/requirements.txt` and can evolve independently of the MCP contract.

## Configuration

Environment variables include:

- `PYTHON_WORKSPACE_HOST`
- `PYTHON_WORKSPACE_PORT`
- `PYTHON_WORKSPACE_API_KEY`
- `PYTHON_WORKSPACE_PATH`
- `PYTHON_WORKSPACE_ID`
- `PYTHON_WORKSPACE_NAME`
- `PYTHON_WORKSPACE_DOCKER_IMAGE`
- `PYTHON_WORKSPACE_DOCKER_CONTAINER`
- `PYTHON_WORKSPACE_PUBLIC_URL`
- `PYTHON_WORKSPACE_EXECUTION_TIMEOUT`
- `PYTHON_WORKSPACE_REQUIRE_AUTH`
- `PYTHON_WORKSPACE_OAUTH_STATE` (OAuth codes/refresh tokens, default `./data/oauth.json`; only used with OIDC)
- the `OIDC_*` variables and `JWT_SECRET` below

## OAuth sign-in with single sign-on (OIDC)

Optional. When `OIDC_ISSUER` is **unset or empty**, nothing below exists: no OAuth or `/oidc/*`
routes (404), no `.well-known` metadata, and authentication works exactly as before (API keys /
`PYTHON_WORKSPACE_API_KEY`, `PYTHON_WORKSPACE_REQUIRE_AUTH`).

When it is set, the server becomes an **OAuth authorization server + resource server for `/mcp`**
(so MCP clients such as ChatGPT or Claude can connect with just the URL) and an **OIDC Relying
Party** toward your identity provider (e.g. authentik). It never issues ID tokens and is not an
OpenID Provider. The flow follows the codestash `mcp/api-connector-style` scaffold:

- CIMD client ids (the `client_id` is the https URL of the client's metadata document), S256 PKCE,
  single-use authorization codes, refresh tokens, public clients (`token_endpoint_auth_method: none`).
- Access tokens are HS256 JWTs with `iss` = `PYTHON_WORKSPACE_PUBLIC_URL` and
  `aud` = `<PYTHON_WORKSPACE_PUBLIC_URL>/mcp`, valid for one hour.
- `/.well-known/oauth-protected-resource/mcp` (RFC 9728, also at the root path),
  `/.well-known/oauth-authorization-server` and the `/.well-known/openid-configuration` alias.
- An unauthenticated `/mcp` request gets `401` with
  `WWW-Authenticate: Bearer resource_metadata="<public URL>/.well-known/oauth-protected-resource/mcp", scope="mcp"`.
  With OIDC on, `PYTHON_WORKSPACE_REQUIRE_AUTH` defaults to `true`; set it to `false` explicitly
  only if anonymous requests should still act as the service user.
- `/oauth/authorize` has no password form: it shows one single sign-on button
  (`/oidc/login?oauth=…`), the provider signs the user in, `/oidc/callback` verifies the ID token
  and shows the consent page (Approve / Deny).
- **API keys keep working** next to OAuth tokens (per-user keys and `PYTHON_WORKSPACE_API_KEY`).

| Variable | Meaning |
|---|---|
| `OIDC_ISSUER` | Issuer URL exactly as the provider publishes it (authentik: `https://auth.example.org/application/o/<slug>/`, keep the trailing slash). Unset = OIDC and OAuth off. Must be `https://` when `PYTHON_WORKSPACE_PUBLIC_URL` is `https://`. |
| `OIDC_CLIENT_ID` | Required when `OIDC_ISSUER` is set. |
| `OIDC_CLIENT_SECRET` | Optional. Set = confidential client (`client_secret_basic`); unset = public client. PKCE is always used. |
| `OIDC_SCOPES` | Default `openid email profile`; must contain `openid`. |
| `OIDC_BUTTON_LABEL` | Button text, default `Sign in with single sign-on`. |
| `OIDC_CREATE_USERS` | `true` = create a local user on the first sign-in of someone who has none. Default `false`. |
| `OIDC_TRUST_EMAIL` | `true` = link to a user by email even when the provider does not say `email_verified: true`. Default `false`. |
| `JWT_SECRET` | Base64, at least 32 bytes (`openssl rand -base64 32`). Signs access tokens and consent tickets. Required when `OIDC_ISSUER` is set. |

Invalid values (missing client id, `OIDC_SCOPES` without `openid`, booleans other than
true/false/1/0/yes/no/on/off, a short `JWT_SECRET`) stop the server at startup. The provider is
contacted lazily on the first sign-in, so the server starts even if it is down.

Redirect URI to register at the provider: `<PYTHON_WORKSPACE_PUBLIC_URL>/oidc/callback`.

### Which local user a sign-in becomes

Workspaces are owned by local users, so every sign-in resolves to one, and the OAuth access token
then resolves to the same principal an API key for that user would:

1. A sign-in already linked to a user (by issuer + `sub`, stored in the state file) is that user.
2. Otherwise, if the provider sends an email that is verified (`email_verified: true`) or
   `OIDC_TRUST_EMAIL=true`, the user with that email (case-insensitive) is linked and used. Give
   users an email with `python-workspace user add <id> <name> --email <email>` or
   `python-workspace user set-email <id> <email>`.
3. Otherwise, with `OIDC_CREATE_USERS=true`, a user `oidc-<hash>` is created (name from `name`,
   `preferred_username` or email; the email is stored only if trusted as in 2.) and linked. It owns
   no workspace until you create one: `python-workspace workspace create <id> <name> <path> <user_id>`.
4. Otherwise the sign-in is refused ("No account for this sign-in; ask the administrator").

Who may sign in at all is decided by the provider (in authentik, the application's policy
bindings); there is no allow-list here. Removing a user (`python-workspace user remove`) removes its
links, and its OAuth tokens and refresh tokens stop working.

The pending sign-in (state, nonce, PKCE verifier) is kept in memory for 10 minutes, single use,
bound to an httpOnly `python_workspace_oidc` cookie (`SameSite=Lax`, `Path=/oidc`, `Secure` when the
public URL is https). A restart during a sign-in just means signing in again. `/oidc/*` is limited to
30 requests per minute per client IP.

### authentik

1. *Applications → Providers → Create → OAuth2/OpenID Provider*: client type **Confidential**,
   redirect URI `<PYTHON_WORKSPACE_PUBLIC_URL>/oidc/callback` (strict), choose a **signing key** so ID
   tokens are RS256, scopes `openid`, `email`, `profile`.
2. *Applications → Create*: link it to the provider; bind policies/groups for who may use it.
3. Copy the **OpenID Configuration Issuer** from the provider page into `OIDC_ISSUER`, and the
   client id / secret into `OIDC_CLIENT_ID` / `OIDC_CLIENT_SECRET`.

See `docs/PLAN.md`, `docs/MCP-INTERFACE.md`, `docs/SECURITY.md` and `docs/DEPLOYMENT-PROFILES.md` for the architecture and roadmap.
