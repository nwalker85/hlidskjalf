# RUNBOOK-009: GitLab SSO with Zitadel

## Overview

This runbook covers setting up GitLab CE with Zitadel OIDC authentication, including:
- Certificate trust configuration
- OIDC provider setup
- Organization and group creation
- Admin permission assignment
- Automated permission sync

---

## Prerequisites

- [ ] Zitadel running and accessible at `zitadel.ravenhelm.test`
- [ ] GitLab CE deployed via docker-compose
- [ ] mkcert CA certificate available
- [ ] Zitadel OIDC application created for GitLab

---

## 1. Zitadel Application Setup

### Create GitLab Application in Zitadel

1. Login to Zitadel admin console: `https://zitadel.ravenhelm.test`
2. Navigate to **Projects** → Select your project (e.g., "Ravenhelm")
3. **Add Application** → Choose "Web"
4. Configuration:
   - **Name**: GitLab
   - **Authentication Method**: Code (PKCE optional)
   - **Redirect URIs**: `https://gitlab.ravenhelm.test/users/auth/openid_connect/callback`
   - **Post Logout URIs**: `https://gitlab.ravenhelm.test`

5. Copy the **Client ID** and **Client Secret**

### Add to `.env`

```bash
GITLAB_OIDC_CLIENT_ID=<your-client-id>
GITLAB_OIDC_CLIENT_SECRET=<your-client-secret>
```

---

## 2. Certificate Trust Configuration

### Problem
GitLab must trust Zitadel's SSL certificate (signed by mkcert CA).

### Solution

1. **Copy mkcert CA to certs directory:**
   ```bash
   cp ~/Library/Application\ Support/mkcert/rootCA.pem \
      ./ravenhelm-proxy/config/certs/mkcert-ca.crt
   ```

2. **Mount in docker-compose.yml:**
   ```yaml
   gitlab:
     entrypoint:
       - /bin/sh
       - -c
       - |
         mkdir -p /etc/gitlab/trusted-certs &&
         cp /certs/mkcert-ca.crt /etc/gitlab/trusted-certs/mkcert-ca.crt &&
         exec /assets/init-container
     volumes:
       - ./ravenhelm-proxy/config/certs/mkcert-ca.crt:/certs/mkcert-ca.crt:ro
   ```

3. **Verify certificate chain:**
   ```bash
   docker exec gitlab-sre-gitlab curl -s https://zitadel.ravenhelm.test/.well-known/openid-configuration | head -1
   ```
   Should return JSON, not SSL errors.

---

## 3. GitLab OIDC Configuration

### docker-compose.yml Environment

```yaml
gitlab:
  environment:
    GITLAB_OIDC_CLIENT_ID: ${GITLAB_OIDC_CLIENT_ID}
    GITLAB_OIDC_CLIENT_SECRET: ${GITLAB_OIDC_CLIENT_SECRET}
    GITLAB_OMNIBUS_CONFIG: |
      # Zitadel SSO (OpenID Connect)
      gitlab_rails['omniauth_enabled'] = true
      gitlab_rails['omniauth_allow_single_sign_on'] = ['openid_connect']
      gitlab_rails['omniauth_block_auto_created_users'] = false
      gitlab_rails['omniauth_auto_link_user'] = ['openid_connect']
      gitlab_rails['omniauth_providers'] = [
        {
          name: "openid_connect",
          label: "Zitadel",
          args: {
            name: "openid_connect",
            scope: ["openid", "profile", "email", "urn:zitadel:iam:org:project:roles"],
            response_type: "code",
            issuer: "https://zitadel.ravenhelm.test",
            discovery: true,
            client_auth_method: "basic",
            uid_field: "sub",
            pkce: true,
            client_options: {
              identifier: ENV["GITLAB_OIDC_CLIENT_ID"],
              secret: ENV["GITLAB_OIDC_CLIENT_SECRET"],
              redirect_uri: "https://gitlab.ravenhelm.test/users/auth/openid_connect/callback"
            }
          }
        }
      ]
```

### Key Settings Explained

| Setting | Value | Purpose |
|---------|-------|---------|
| `omniauth_block_auto_created_users` | `false` | Allow new users immediately |
| `omniauth_auto_link_user` | `['openid_connect']` | Link existing users by email |
| `scope` | `urn:zitadel:iam:org:project:roles` | Request Zitadel roles in token |
| `pkce` | `true` | Enhanced security for auth flow |

---

## 4. Network Configuration

### Traefik Routing

Add to `ravenhelm-proxy/dynamic.yml`:

```yaml
http:
  routers:
    gitlab:
      rule: "Host(`gitlab.ravenhelm.test`)"
      service: gitlab-svc
      tls: {}

  services:
    gitlab-svc:
      loadBalancer:
        servers:
          - url: "http://gitlab-sre-gitlab:80"
```

### Connect to Traefik Network

```bash
docker network connect ravenhelm-network gitlab-sre-gitlab
```

---

## 5. Organization & Group Setup

### Create Organization (GitLab 17+)

```bash
docker exec gitlab-sre-gitlab gitlab-rails runner '
org = Organizations::Organization.find_by(path: "ravenhelm")
unless org
  org = Organizations::Organization.create!(
    name: "Ravenhelm",
    path: "ravenhelm",
    visibility_level: 0
  )
  puts "Created organization: #{org.name}"
end
'
```

### Create Group

```bash
docker exec gitlab-sre-gitlab gitlab-rails runner '
org = Organizations::Organization.find_by(path: "ravenhelm")
group = Group.find_by(path: "ravenhelm")
unless group
  group = Group.create!(
    name: "Ravenhelm",
    path: "ravenhelm",
    description: "Ravenhelm Platform Development",
    visibility_level: 0,
    organization: org
  )
  puts "Created group: #{group.name}"
end
'
```

---

## 6. Admin Permission Assignment

### Manual Assignment (after SSO login)

```bash
docker exec gitlab-sre-gitlab gitlab-rails runner '
user = User.find_by(email: "nate@ravenhelm.co")
user.admin = true
user.save!
puts "#{user.username} is now admin"
'
```

### Add User to Group as Owner

```bash
docker exec gitlab-sre-gitlab gitlab-rails runner '
user = User.find_by(email: "nate@ravenhelm.co")
group = Group.find_by(path: "ravenhelm")
unless group.members.exists?(user_id: user.id)
  group.add_member(user, Gitlab::Access::OWNER)
  puts "Added #{user.username} as Owner of #{group.name}"
end
'
```

### List All Users

```bash
docker exec gitlab-sre-gitlab gitlab-rails runner '
User.all.each { |u| puts "#{u.username}: #{u.email} (admin: #{u.admin})" }
'
```

---

## 7. Generate Admin API Token

For automation, create a personal access token:

```bash
docker exec gitlab-sre-gitlab gitlab-rails runner '
user = User.find_by(admin: true)
token = user.personal_access_tokens.create!(
  name: "Norns Automation",
  scopes: ["api", "read_user", "read_api", "read_repository", "write_repository", "sudo"],
  expires_at: 1.year.from_now
)
puts "Token: #{token.token}"
puts "Store this securely - it will not be shown again!"
'
```

Store the token in `.env`:
```bash
GITLAB_API_TOKEN=<token>
```

---

## 8. Automated Permission Sync (Future)

### Architecture

```
┌─────────────┐     webhook      ┌─────────────┐     query      ┌─────────────┐
│   GitLab    │ ───────────────▶ │    Norns    │ ─────────────▶ │   Zitadel   │
│ user_create │                  │  GitLab     │                │  User Roles │
└─────────────┘                  │  Agent      │                └─────────────┘
                                 └──────┬──────┘
                                        │ API call
                                        ▼
                                 ┌─────────────┐
                                 │   GitLab    │
                                 │  Set Admin  │
                                 │  Add Group  │
                                 └─────────────┘
```

### Webhook Setup

1. In GitLab: **Admin** → **System Hooks**
2. URL: `https://hlidskjalf-api.ravenhelm.test/api/v1/webhooks/gitlab`
3. Trigger: `user_create`

### Role Mapping

| Zitadel Role | GitLab Permission |
|--------------|-------------------|
| `admin` | Site Admin |
| `developer` | Developer in Ravenhelm group |
| `operator` | Maintainer in Ravenhelm group |
| `viewer` | Guest in Ravenhelm group |

---

## Troubleshooting

### SSL Certificate Errors

```bash
# Check if CA is installed
docker exec gitlab-sre-gitlab ls -la /etc/gitlab/trusted-certs/

# Verify SSL connection
docker exec gitlab-sre-gitlab curl -v https://zitadel.ravenhelm.test/ 2>&1 | grep -E "SSL|cert"

# Force reconfigure to reload certs
docker exec gitlab-sre-gitlab gitlab-ctl reconfigure
```

### OIDC Discovery Fails

```bash
# Test OIDC endpoint from GitLab container
docker exec gitlab-sre-gitlab curl -s https://zitadel.ravenhelm.test/.well-known/openid-configuration | jq .issuer
```

### User Not Created

Check GitLab logs:
```bash
docker logs gitlab-sre-gitlab 2>&1 | grep -i "omniauth\|oidc" | tail -20
```

### Network Issues

```bash
# Verify GitLab is on ravenhelm-network
docker inspect gitlab-sre-gitlab | jq '.[0].NetworkSettings.Networks | keys'

# Test internal resolution
docker exec gitlab-sre-gitlab getent hosts zitadel.ravenhelm.test
```

---

## Verification Checklist

- [ ] GitLab accessible at `https://gitlab.ravenhelm.test`
- [ ] "Sign in with Zitadel" button visible
- [ ] SSO login redirects to Zitadel
- [ ] User created in GitLab after first login
- [ ] User can be promoted to admin
- [ ] Ravenhelm organization exists
- [ ] Ravenhelm group exists under organization
- [ ] Admin API token generated and stored

---

## Related Runbooks

- [RUNBOOK-006: Zitadel SSO](./RUNBOOK-006-zitadel-sso.md)
- [RUNBOOK-002: Add Traefik Domain](./RUNBOOK-002-add-traefik-domain.md)
- [RUNBOOK-003: Generate Certificates](./RUNBOOK-003-generate-certificates.md)

