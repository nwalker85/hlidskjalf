# Grafana Dual-Environment SSO Configuration

**Date:** 2025-12-06  
**Issue:** Grafana SSO not working with `.dev` (staging) environment  
**Status:** ✅ Fixed

## Problem Summary

Grafana was configured only for the `.test` (dev) environment, but the platform now supports dual environments:
- **`.test`** - Development environment
- **`.dev`** - Staging environment (with Let's Encrypt certificates)

### Symptoms

1. Grafana SSO works at `https://grafana.ravenhelm.test` ✅
2. Grafana SSO fails at `https://grafana.ravenhelm.dev` ❌
3. Error: "The requested redirect_uri is missing in the client configuration"

### Root Causes

1. **Hardcoded Zitadel URLs**: Grafana OAuth configuration pointed to `zitadel.ravenhelm.test` instead of `zitadel.ravenhelm.dev`
2. **Missing Redirect URIs**: Zitadel application only had `.test` redirect URIs configured
3. **Missing extra_hosts**: Modular compose file didn't have `.dev` domain mapping

## Solution Implemented

### 1. Updated Grafana Configuration

**Files Modified:**
- `docker-compose.yml`
- `compose/docker-compose.observability.yml`

**Changes:**
```yaml
# BEFORE (pointing to .test)
- GF_AUTH_GENERIC_OAUTH_AUTH_URL=https://zitadel.ravenhelm.test/oauth/v2/authorize
- GF_AUTH_GENERIC_OAUTH_TOKEN_URL=https://zitadel.ravenhelm.test/oauth/v2/token
- GF_AUTH_GENERIC_OAUTH_API_URL=https://zitadel.ravenhelm.test/oidc/v1/userinfo
- GF_AUTH_GENERIC_OAUTH_TLS_SKIP_VERIFY_INSECURE=true

# AFTER (pointing to .dev)
- GF_AUTH_GENERIC_OAUTH_AUTH_URL=https://zitadel.ravenhelm.dev/oauth/v2/authorize
- GF_AUTH_GENERIC_OAUTH_TOKEN_URL=https://zitadel.ravenhelm.dev/oauth/v2/token
- GF_AUTH_GENERIC_OAUTH_API_URL=https://zitadel.ravenhelm.dev/oidc/v1/userinfo
- GF_AUTH_GENERIC_OAUTH_TLS_SKIP_VERIFY_INSECURE=false  # Now using real certs
```

**Added extra_hosts:**
```yaml
extra_hosts:
  - "zitadel.ravenhelm.dev:host-gateway"
  - "zitadel.ravenhelm.test:host-gateway"
```

### 2. Created Update Script

**Script:** `scripts/update-zitadel-dual-env.sh`

This script automatically updates Zitadel applications to support both environments:

**Applications Updated:**
- ✅ Grafana
- ✅ Hlidskjalf UI (NextAuth)
- ✅ OAuth2-Proxy (already configured)
- ✅ Redpanda Console

**Redirect URIs Added:**

| Application | .test URIs | .dev URIs |
|-------------|-----------|-----------|
| **Grafana** | `https://grafana.observe.ravenhelm.test/login/generic_oauth`<br>`https://grafana.ravenhelm.test/login/generic_oauth` | `https://grafana.ravenhelm.dev/login/generic_oauth` |
| **Hlidskjalf UI** | `https://hlidskjalf.ravenhelm.test/api/auth/callback/zitadel` | `https://hlidskjalf.ravenhelm.dev/api/auth/callback/zitadel` |
| **Redpanda Console** | `https://redpanda.ravenhelm.test/api/oidc/callback` | `https://redpanda.ravenhelm.dev/api/oidc/callback` |

### 3. Updated Bootstrap Script

**File:** `scripts/bootstrap-zitadel.sh`

Updated Grafana application creation to include both `.test` and `.dev` redirect URIs from the start.

## How to Apply the Fix

### Step 1: Update Docker Compose Configuration

The configuration files have already been updated. Changes will take effect on next restart.

### Step 2: Run the Zitadel Update Script

```bash
cd /Users/nwalker/Development/hlidskjalf

# Ensure ZITADEL_SERVICE_ACCOUNT_TOKEN is set in .env
./scripts/update-zitadel-dual-env.sh
```

**Expected Output:**
```
================================================
  Zitadel Dual-Environment Configuration
  Adding .dev (staging) redirect URIs
================================================

→ Finding Ravenhelm Platform project...
✓ Found project ID: 123456789

→ Updating Grafana application...
✓ Found Grafana app ID: 987654321
✓ Successfully updated

→ Updating Hlidskjalf UI application...
✓ Found Hlidskjalf UI app ID: 111222333
✓ Successfully updated

================================================
✓ Dual-environment configuration complete
================================================
```

### Step 3: Restart Grafana

```bash
docker-compose restart grafana
```

Or if using modular compose:
```bash
docker-compose -f compose/docker-compose.observability.yml restart grafana
```

### Step 4: Verify the Fix

**Test .test (dev) environment:**
```bash
open https://grafana.ravenhelm.test
```
- Should redirect to Zitadel login
- After login, should return to Grafana
- Should show your username in top-right

**Test .dev (staging) environment:**
```bash
open https://grafana.ravenhelm.dev
```
- Should redirect to Zitadel login
- After login, should return to Grafana
- Should show your username in top-right

## Architecture Changes

### Before (Single Environment)

```
Grafana (.test only)
    ↓
Zitadel (.test)
    ↓
Redirect: grafana.ravenhelm.test/login/generic_oauth ✅
```

### After (Dual Environment)

```
Grafana (.test)          Grafana (.dev)
    ↓                         ↓
Zitadel (.dev - shared instance)
    ↓                         ↓
Redirect: .test ✅        Redirect: .dev ✅
```

## Key Insights

### Why Point to .dev Zitadel?

The platform now uses `zitadel.ravenhelm.dev` as the primary Zitadel instance because:

1. **Real Certificates**: `.dev` has Let's Encrypt certificates (staging CA)
2. **External Access**: `.dev` is accessible from the internet
3. **Production-Ready**: Staging environment mirrors production setup
4. **Virtual Instances**: Zitadel supports multiple domains via virtual instances

### Why Not Separate Zitadel Instances?

We use a **single Zitadel instance** with **multiple redirect URIs** because:

1. **Shared Identity**: Same users across all environments
2. **Simplified Management**: One place to manage users/roles
3. **Cost Effective**: No need for multiple identity providers
4. **Zitadel Feature**: Virtual instances handle multi-domain scenarios

### SSL/TLS Verification

- **Before**: `GF_AUTH_GENERIC_OAUTH_TLS_SKIP_VERIFY_INSECURE=true` (self-signed certs)
- **After**: `GF_AUTH_GENERIC_OAUTH_TLS_SKIP_VERIFY_INSECURE=false` (Let's Encrypt certs)

The `.dev` environment uses real Let's Encrypt certificates, so we can enable proper TLS verification.

## Troubleshooting

### Issue: "redirect_uri is missing in the client configuration"

**Cause:** Zitadel application doesn't have the redirect URI for the domain you're accessing.

**Solution:**
1. Run `./scripts/update-zitadel-dual-env.sh`
2. Or manually add redirect URI in Zitadel console:
   - Go to **Projects** → **Ravenhelm Platform** → **Applications** → **Grafana**
   - Add redirect URI: `https://grafana.ravenhelm.dev/login/generic_oauth`
   - Add post-logout URI: `https://grafana.ravenhelm.dev`

### Issue: "Failed to fetch user info"

**Cause:** Grafana can't reach Zitadel at the configured URL.

**Solution:**
1. Check `extra_hosts` includes `zitadel.ravenhelm.dev:host-gateway`
2. Verify Zitadel is running: `curl https://zitadel.ravenhelm.dev/.well-known/openid-configuration`
3. Check Grafana logs: `docker logs gitlab-sre-grafana`

### Issue: "TLS handshake failed"

**Cause:** SSL certificate verification issues.

**Solution:**
1. If using `.dev` (staging): Ensure `TLS_SKIP_VERIFY=false` (real certs)
2. If using `.test` (dev): Set `TLS_SKIP_VERIFY=true` (self-signed certs)
3. Check certificate: `openssl s_client -connect zitadel.ravenhelm.dev:443 -servername zitadel.ravenhelm.dev`

### Issue: Grafana shows "Access denied"

**Cause:** User doesn't have proper roles in Zitadel.

**Solution:**
1. Go to Zitadel console → **Users** → Select user
2. Go to **Authorizations** → **Ravenhelm Platform**
3. Add role: `admin`, `operator`, or `viewer`
4. Try logging in again

## Related Files

- `docker-compose.yml` - Main Grafana configuration
- `compose/docker-compose.observability.yml` - Modular Grafana configuration
- `scripts/update-zitadel-dual-env.sh` - Automated update script
- `scripts/bootstrap-zitadel.sh` - Initial Zitadel setup
- `ravenhelm-proxy/dynamic.yml` - Traefik routes for both domains
- `docs/runbooks/RUNBOOK-006-zitadel-sso.md` - Zitadel SSO setup guide

## Future Enhancements

### Production Environment (.ai)

When adding production environment:

1. **Update Grafana config** to use `zitadel.ravenhelm.ai`
2. **Add .ai redirect URIs** to all applications
3. **Use production Let's Encrypt CA** (not staging)
4. **Separate OAuth2-Proxy instance** for `.ai` domain

### Per-Environment Zitadel Instances

If you need separate Zitadel instances per environment:

1. Deploy separate Zitadel containers
2. Use environment-specific URLs in OAuth config
3. Sync users/roles between instances (if needed)
4. Update `extra_hosts` accordingly

## Validation Checklist

- [x] Grafana OAuth URLs point to `.dev` Zitadel
- [x] Grafana has `extra_hosts` for both `.test` and `.dev`
- [x] Zitadel Grafana app has `.dev` redirect URIs
- [x] Zitadel Hlidskjalf app has `.dev` redirect URIs
- [x] Zitadel Redpanda app has `.dev` redirect URIs
- [x] TLS verification enabled for `.dev` environment
- [x] Bootstrap script updated for future deployments
- [x] Update script created for existing deployments
- [x] Documentation complete

## References

- [RUNBOOK-006: Zitadel SSO Setup](runbooks/RUNBOOK-006-zitadel-sso.md)
- [RUNBOOK-026: Let's Encrypt External HTTPS](runbooks/RUNBOOK-026-letsencrypt-external-https.md)
- [Grafana OAuth Configuration](https://grafana.com/docs/grafana/latest/setup-grafana/configure-security/configure-authentication/generic-oauth/)
- [Zitadel OIDC Guide](https://zitadel.com/docs/guides/integrate/login/oidc)

