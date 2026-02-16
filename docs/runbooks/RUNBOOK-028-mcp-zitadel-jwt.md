# RUNBOOK-028: Obtain Zitadel JWTs for MCP

## Purpose

Agents and tools (e.g., Norns, Bifrost, CLI users) must present a Zitadel-issued OAuth 2.1 token when calling the MCP GitLab server at `https://mcp.gitlab.ravenhelm.test`. This runbook covers:

1. Creating or locating the correct client credentials in Zitadel.
2. Minting a JWT with the `mcp.gitlab.manage` scope (plus optional narrow scopes).
3. Using that JWT in `/tools/list` or `/tools/call` requests against the MCP endpoint.

---

## 1. Prerequisites

1. Zitadel admin access (console or service account token with management APIs).
2. `ZITADEL_SERVICE_ACCOUNT_TOKEN` and `ZITADEL_PROJECT_ID` exported (see `scripts/bootstrap-zitadel.sh` or `docs/runbooks/RUNBOOK-006-zitadel-sso.md`).
3. Knowledge of the agent/client that will call MCP so you can assign the appropriate scope/audience.

---

## 2. Create / Inspect OAuth Client

Most platform services already have OIDC clients created by `scripts/bootstrap-zitadel.sh`. To mint a token for a new automation client:

1. Sign in to Zitadel Console (`https://zitadel.ravenhelm.test/ui/console`).
2. Navigate to **Projects** → **Ravenhelm Platform** → **Applications** → **+ New** → **Machine** (or use the CLI API below).
3. Set redirect URIs (for machine apps, `http://localhost` is fine). Enable the scopes you need:
   - `openid`
   - `profile`
   - `mcp.gitlab.manage` (custom scope created during bootstrap)
4. Save the client ID and client secret.

### CLI Example (optional)

```bash
source .env  # must export ZITADEL_SERVICE_ACCOUNT_TOKEN, ZITADEL_PROJECT_ID

# Create machine user + PAT (reuse RUNBOOK-006 function)
curl -sk -X POST \
  -H "Authorization: Bearer $ZITADEL_SERVICE_ACCOUNT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"userName":"mcp-cli","name":"MCP CLI","accessTokenType":"ACCESS_TOKEN_TYPE_JWT"}' \
  "https://zitadel.ravenhelm.test/management/v1/users/machine"

# Create OAuth client (simplified)
curl -sk -X POST \
  -H "Authorization: Bearer $ZITADEL_SERVICE_ACCOUNT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
        "name": "MCP CLI",
        "appType": "OIDC_APP_TYPE_WEB",
        "authMethodType": "OIDC_AUTH_METHOD_TYPE_BASIC",
        "redirectUris": ["http://localhost"],
        "responseTypes": ["OIDC_RESPONSE_TYPE_CODE"],
        "grantTypes": ["OIDC_GRANT_TYPE_CLIENT_CREDENTIALS"]
      }' \
  "https://zitadel.ravenhelm.test/management/v1/projects/$ZITADEL_PROJECT_ID/apps/oidc"
```

---

## 3. Obtain JWT via Client Credentials

### Using `curl`

```bash
export MCP_CLIENT_ID=<client_id>
export MCP_CLIENT_SECRET=<client_secret>

curl -sk -X POST https://zitadel.ravenhelm.test/oauth/v2/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials&client_id=${MCP_CLIENT_ID}&client_secret=${MCP_CLIENT_SECRET}&scope=openid%20profile%20mcp.gitlab.manage"
```

Response:

```json
{
  "access_token": "eyJraWQiOi...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "scope": "openid profile mcp.gitlab.manage"
}
```

Copy the `access_token`.

### Using `zitadel` CLI (optional)

If you installed the Zitadel CLI:

```bash
zitadel token client-key \
  --client-id $MCP_CLIENT_ID \
  --client-secret $MCP_CLIENT_SECRET \
  --scopes "openid profile mcp.gitlab.manage"
```

---

## 4. Call MCP with the JWT

The MCP server requires the JWT in the `Authorization` header. Example tool call:

```bash
export MCP_TOKEN=<access_token>

curl -sk https://mcp.gitlab.ravenhelm.test/tools/call \
  -H "Authorization: Bearer $MCP_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
        "name": "gitlab.projects.create",
        "arguments": {
          "name": "demo-service",
          "group_path": "ravenhelm/projects",
          "visibility": "private"
        }
      }'
```

List available tools:

```bash
curl -sk https://mcp.gitlab.ravenhelm.test/tools/list \
  -H "Authorization: Bearer $MCP_TOKEN"
```

If you omit the token or scope, Traefik returns `401`/`403` before the request reaches MCP.

---

## 5. Scoping Guidelines

- **Default scope** for GitLab automation is `mcp.gitlab.manage`. Add narrower scopes later when more policies exist (e.g., `mcp.gitlab.read_only`).
- The JWT’s `aud` claim is optional for now but can be set to the MCP client ID (set `OAUTH_AUDIENCE` in `services/mcp-server-gitlab` if you want to enforce it).
- Service accounts used for MCP should live in the Ravenhelm project and only carry the minimal roles needed to administer GitLab/Zitadel/Docker.

---

## 6. Troubleshooting

| Symptom | Likely Cause | Resolution |
|---------|--------------|------------|
| `401 Unauthorized` from Traefik | Missing login via oauth2-proxy or invalid JWT | Re-authenticate, ensure `mcp.gitlab.manage` scope present. |
| `401`/`403` JSON from MCP | Missing/invalid `Authorization` header | Pass `Bearer <token>` header with client credentials token. |
| `invalid_client` from Zitadel | Wrong client secret or auth method | Confirm client type; machine clients usually use `client_secret_basic`. |
| `insufficient_scope` | Token lacks `mcp.gitlab.manage` | Reissue token with proper scope. |

---

## References

- `docs/runbooks/RUNBOOK-006-zitadel-sso.md`
- `docs/runbooks/RUNBOOK-023-mcp-gitlab-server.md`
- `scripts/bootstrap-zitadel.sh`


