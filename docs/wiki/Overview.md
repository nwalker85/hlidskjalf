# Overview & Governance

## Mission Snapshot
- **Purpose:** Hliðskjálf is the Ravenhelm control plane for deploying and operating multi-agent platforms across environments.
- **Source of truth:** `PROJECT_PLAN.md` (phased roadmap) and `docs/EXECUTIVE_SUMMARY.md` (stakeholder view).
- **Key tenets:** Environment-first architecture, zero-trust security, multi-model AI, evidence-first compliance.

## Quick Links
- [Project Plan (repo)](../PROJECT_PLAN.md)
- [Executive Summary (repo)](../docs/EXECUTIVE_SUMMARY.md)
- [Architecture Index](Architecture_Index.md)
- [Runbook Catalog](Runbook_Catalog.md)

## Governance Checklist
1. **Architecture Alignment:** Validate new changes against the Enterprise Scaffold v1.3.0 (`/Users/nwalker/Documents/Enterprise_MultiPlatform_Architecture_Scaffold_v1.3.0.md`).
2. **Environment Readiness:** Ensure dev/staging/prod separation is preserved in Terraform/Docker configs.
3. **Security Review:** Confirm SPIRE identities, Zitadel scopes, and Traefik routing updates have corresponding runbooks.
4. **Documentation Flow:** Every major change needs a wiki touchpoint plus references back to `docs/`.
5. **Board Sync:** Issues must live on the Operations Board with `status::` labels to reflect progress.

