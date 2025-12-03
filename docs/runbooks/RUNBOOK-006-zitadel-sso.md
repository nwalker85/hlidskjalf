# RUNBOOK-006: Zitadel SSO Configuration

> **Purpose**: Configure Single Sign-On (SSO) for all platform services using Zitadel as the Identity Provider.

---

## Overview

Zitadel provides OAuth 2.1/OIDC-based authentication for:
- **Human users**: SSO login to Grafana, Hliðskjálf UI, LangFuse, GitLab
- **Machine accounts**: Service accounts for Norns AI, automation (Skuld)

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ZITADEL SSO ARCHITECTURE                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│    HUMANS                                                                   │
│    ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐                      │
│    │ Grafana │  │Hliðskjálf│  │LangFuse │  │ GitLab  │                      │
│    │  (SSO)  │  │  (SSO)   │  │  (SSO)  │  │  (SSO)  │                      │
│    └────┬────┘  └────┬─────┘  └────┬────┘  └────┬────┘                      │
│         │            │             │            │                            │
│         └────────────┴──────┬──────┴────────────┘                            │
│                             │                                                │
│                             ▼                                                │
│                   ┌─────────────────────┐                                   │
│                   │       ZITADEL       │                                   │
│                   │  Identity Provider  │                                   │
│                   │                     │                                   │
│                   │  • OIDC/OAuth 2.1   │                                   │
│                   │  • Role-based access│                                   │
│                   │  • Service accounts │                                   │
│                   └─────────────────────┘                                   │
│                             ▲                                                │
│         ┌────────────┬──────┴───────┬────────────┐                          │
│         │            │              │            │                          │
│    ┌────┴────┐  ┌────┴────┐   ┌────┴────┐  ┌────┴────┐                     │
│    │  Skuld  │  │  Norns  │   │ API     │  │ Future  │                     │
│    │(Automate)│  │ (Agent) │   │Clients  │  │Services │                     │
│    └─────────┘  └─────────┘   └─────────┘  └─────────┘                     │
│    MACHINES                                                                  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Prerequisites

- Zitadel running at `https://zitadel.ravenhelm.test`
- Admin access to Zitadel console
- Traefik configured for `*.ravenhelm.test` domains
- Service accounts for automation (Skuld)

---

## Part 1: Initial Zitadel Setup

### 1.1 Start Zitadel

```bash
cd /path/to/hlidskjalf
docker compose up -d zitadel
```

### 1.2 First Login

1. Navigate to `https://zitadel.ravenhelm.test`
2. Login with default admin:
   - Username: `zitadel-admin@zitadel.ravenhelm.test`
   - Password: (set in `ZITADEL_FIRSTINSTANCE_ORG_HUMAN_PASSWORD`)

### 1.3 Create Human Users

1. Go to **Users** → **Users**
2. Click **+ New**
3. Fill in:
   - First Name: (e.g., "Nate")
   - Last Name: (e.g., "Walker")
   - Email: (e.g., "nate@ravenhelm.co")
   - Username: (auto-generated or custom)
4. Set password or send invite

### 1.4 Create Service Account (Automation)

Used for API automation (bootstrap scripts, CI/CD):

1. Go to **Users** → **Service Users**
2. Click **+ New**
3. Fill in:
   - User Name: `skuld` (the Norn of the future)
   - Name: `Skuld Automation`
   - Access Token Type: **JWT**
4. Create a **Personal Access Token**:
   - Go to user → **Personal Access Tokens**
   - Click **+ New**
   - Set expiration (or leave empty for no expiry)
   - **Save the token immediately** (shown only once)

5. Add to `.env`:
   ```bash
   ZITADEL_SERVICE_ACCOUNT_ID=<user_id>
   ZITADEL_SERVICE_ACCOUNT_TOKEN=<pat_token>
   ```

6. Grant **Org Owner** role:
   - Go to **Organization** → **Members**
   - Add `skuld` with `Org Owner` role

---

## Part 2: Create Ravenhelm Project

### 2.1 Via Console

1. Go to **Projects** → **+ New Project**
2. Name: `Ravenhelm Platform`
3. Enable:
   - **Assert Roles on Authentication**: ✅
   - **Check Roles on Authentication**: ✅

### 2.2 Via API (using bootstrap script)

```bash
./scripts/bootstrap-zitadel.sh
```

This creates:
- Project: `Ravenhelm Platform`
- Roles: `admin`, `developer`, `operator`, `viewer`
- OIDC applications for all services
- Saves credentials to `.zitadel-apps.env`

---

## Part 3: Create Project Roles

In the **Ravenhelm Platform** project:

| Role | Description | Permissions |
|------|-------------|-------------|
| `admin` | Full platform access | All services, all actions |
| `developer` | Development access | Create projects, deploy |
| `operator` | Operations access | Monitor, restart, logs |
| `viewer` | Read-only access | View dashboards only |

To create via console:
1. Go to **Projects** → **Ravenhelm Platform** → **Roles**
2. Click **+ New**
3. Add each role with a display name

---

## Part 4: Configure Services for SSO

### 4.1 Grafana

**OIDC App Type**: Web (confidential client)

**docker-compose.yml**:
```yaml
grafana:
  environment:
    - GF_AUTH_GENERIC_OAUTH_ENABLED=true
    - GF_AUTH_GENERIC_OAUTH_NAME=Zitadel
    - GF_AUTH_GENERIC_OAUTH_CLIENT_ID=${GRAFANA_OIDC_CLIENT_ID}
    - GF_AUTH_GENERIC_OAUTH_CLIENT_SECRET=${GRAFANA_OIDC_CLIENT_SECRET}
    - GF_AUTH_GENERIC_OAUTH_SCOPES=openid profile email urn:zitadel:iam:org:project:roles
    - GF_AUTH_GENERIC_OAUTH_AUTH_URL=https://zitadel.ravenhelm.test/oauth/v2/authorize
    - GF_AUTH_GENERIC_OAUTH_TOKEN_URL=http://zitadel:8080/oauth/v2/token
    - GF_AUTH_GENERIC_OAUTH_API_URL=http://zitadel:8080/oidc/v1/userinfo
    - GF_AUTH_GENERIC_OAUTH_ROLE_ATTRIBUTE_PATH=contains(keys('urn:zitadel:iam:org:project:roles'), 'admin') && 'Admin' || contains(keys('urn:zitadel:iam:org:project:roles'), 'developer') && 'Editor' || 'Viewer'
  extra_hosts:
    - "zitadel.ravenhelm.test:host-gateway"
```

**Redirect URIs**:
- `https://grafana.observe.ravenhelm.test/login/generic_oauth`

### 4.2 Hliðskjálf UI (Next.js + NextAuth)

**OIDC App Type**: Web (confidential client)

**docker-compose.yml**:
```yaml
hlidskjalf-ui:
  environment:
    - AUTH_ZITADEL_ISSUER=https://zitadel.ravenhelm.test
    - AUTH_ZITADEL_CLIENT_ID=${NEXTAUTH_HLIDSKJALF_CLIENT_ID}
    - AUTH_ZITADEL_CLIENT_SECRET=${NEXTAUTH_HLIDSKJALF_CLIENT_SECRET}
    - NEXTAUTH_URL=https://hlidskjalf.ravenhelm.test
    - NEXTAUTH_SECRET=${NEXTAUTH_SECRET}
    - AUTH_TRUST_HOST=true
  extra_hosts:
    - "zitadel.ravenhelm.test:host-gateway"
```

**Redirect URIs**:
- `https://hlidskjalf.ravenhelm.test/api/auth/callback/zitadel`

### 4.3 LangFuse

**OIDC App Type**: Web (confidential client)

**docker-compose.yml**:
```yaml
langfuse:
  environment:
    - AUTH_CUSTOM_CLIENT_ID=${LANGFUSE_OIDC_CLIENT_ID}
    - AUTH_CUSTOM_CLIENT_SECRET=${LANGFUSE_OIDC_CLIENT_SECRET}
    - AUTH_CUSTOM_ISSUER=https://zitadel.ravenhelm.test
    - AUTH_CUSTOM_NAME=Zitadel
  extra_hosts:
    - "zitadel.ravenhelm.test:host-gateway"
```

**Redirect URIs**:
- `https://langfuse.observe.ravenhelm.test/api/auth/callback/custom`

### 4.4 GitLab

**OIDC App Type**: Web (confidential client)

**Redirect URIs**:
- `https://gitlab.ravenhelm.test/users/auth/openid_connect/callback`

Configure in GitLab `gitlab.rb` or via environment.

---

## Part 5: Grant Roles to Users

### 5.1 Via Console

1. Go to **Projects** → **Ravenhelm Platform** → **Authorizations**
2. Click **+ New**
3. Select user
4. Select roles (e.g., `admin`)

### 5.2 Via API

```bash
source .env
curl -sk -X POST \
  -H "Authorization: Bearer $ZITADEL_SERVICE_ACCOUNT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "userId": "USER_ID",
    "projectId": "'"$ZITADEL_PROJECT_ID"'",
    "roleKeys": ["admin"]
  }' \
  "https://zitadel.ravenhelm.test/management/v1/users/USER_ID/grants"
```

---

## Part 6: Role Mapping

### Grafana Role Mapping

Grafana maps Zitadel roles to Grafana roles using JMESPath:

```
GF_AUTH_GENERIC_OAUTH_ROLE_ATTRIBUTE_PATH=contains(keys('urn:zitadel:iam:org:project:roles'), 'admin') && 'Admin' || contains(keys('urn:zitadel:iam:org:project:roles'), 'developer') && 'Editor' || 'Viewer'
```

| Zitadel Role | Grafana Role |
|--------------|--------------|
| `admin` | Admin |
| `developer` | Editor |
| `operator` | Viewer |
| `viewer` | Viewer |

---

## Part 7: Machine Authentication

### 7.1 Create Machine User

```bash
source .env
curl -sk -X POST \
  -H "Authorization: Bearer $ZITADEL_SERVICE_ACCOUNT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "userName": "norns-agent",
    "name": "Norns AI Agent",
    "description": "Service account for Norns",
    "accessTokenType": "ACCESS_TOKEN_TYPE_JWT"
  }' \
  "https://zitadel.ravenhelm.test/management/v1/users/machine"
```

### 7.2 Create Personal Access Token

```bash
USER_ID=<machine_user_id>
curl -sk -X POST \
  -H "Authorization: Bearer $ZITADEL_SERVICE_ACCOUNT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"scopes": ["openid", "profile"]}' \
  "https://zitadel.ravenhelm.test/management/v1/users/$USER_ID/pats"
```

Save the token to `.env`.

### 7.3 Grant Project Roles

```bash
curl -sk -X POST \
  -H "Authorization: Bearer $ZITADEL_SERVICE_ACCOUNT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "userId": "'"$USER_ID"'",
    "projectId": "'"$ZITADEL_PROJECT_ID"'",
    "roleKeys": ["developer", "operator"]
  }' \
  "https://zitadel.ravenhelm.test/management/v1/users/$USER_ID/grants"
```

---

## Troubleshooting

### "Instance not found" Error

**Cause**: Service is trying to reach Zitadel via internal hostname but Zitadel expects external domain.

**Fix**: Add `extra_hosts` to resolve external domain to Docker host:
```yaml
extra_hosts:
  - "zitadel.ravenhelm.test:host-gateway"
```

### Token URL vs Auth URL

- **Auth URL** (browser redirects): Use external domain `https://zitadel.ravenhelm.test`
- **Token URL** (server-to-server): Use internal Docker URL `http://zitadel:8080`

### Roles Not Appearing in Token

1. Ensure roles are created in project
2. Ensure user has grants for those roles
3. Ensure scope includes `urn:zitadel:iam:org:project:roles`
4. Verify project has "Assert Roles on Authentication" enabled

### Login Works But No Admin Access

1. Check role mapping expression in service config
2. Verify user has correct roles in Zitadel
3. Check if roles are in the token:
   ```bash
   # Decode JWT at jwt.io or:
   echo $TOKEN | cut -d'.' -f2 | base64 -d | jq '.'
   ```

---

## Service Accounts Summary

| Account | Purpose | Roles | Token Location |
|---------|---------|-------|----------------|
| `skuld` | Automation/Bootstrap | Org Owner | `ZITADEL_SERVICE_ACCOUNT_TOKEN` |
| `norns-agent` | AI Agent | developer, operator | `NORNS_SERVICE_ACCOUNT_TOKEN` |

---

## Credentials Files

| File | Purpose | Contains |
|------|---------|----------|
| `.env` | Main environment | All service credentials |
| `.zitadel-apps.env` | Bootstrap output | OIDC client IDs and secrets |

---

## Related Runbooks

- **RUNBOOK-004**: SPIRE Management (mTLS)
- **RUNBOOK-005**: File Ownership
- **RUNBOOK-007**: Observability Setup

---

## Version

- **Created**: December 2025
- **Zitadel Version**: v2.62.1 (pinned for built-in login UI)
- **Author**: Ravenhelm Platform Team
