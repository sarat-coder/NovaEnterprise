# Change Management Policy

**Version:** 1.4  
**Effective date:** 2026-05-01  
**Owner:** SRE  
**Last reviewed:** 2026-10-01  

---

## Purpose

This policy governs how production changes — code deployments, configuration updates, infrastructure changes, and dependency upgrades — are planned, reviewed, and deployed at NovaEnterprise.

## Change Categories

| Category | Examples | Review Required | Staging Soak | Production Window |
|----------|----------|----------------|-------------|-------------------|
| Standard | Code deployment, feature flag | Pull request review | 15 minutes | Business hours |
| Significant | Dependency upgrade, schema migration | Pull request + SRE review | 30 minutes | Business hours |
| Emergency | Hotfix for active SEV1/SEV2 | Incident commander approval | As feasible | Any time |
| High-risk | Network policy, IAM policy, database migration | PR + SRE lead + affected team lead | 1 hour | Business hours only |

## Network Policy Changes

Following INC-2036 (September 2026), all Kubernetes network policy changes are classified as **High-risk** and require:

1. Pull request opened on the `infra-configs` repository.
2. Review by at least one SRE lead and one member of the impacted service team.
3. Deployment to `staging` with a 30-minute soak period.
4. Deployment to `production` only during business hours (09:00–17:00 UTC, Monday–Friday).
5. Post-deployment verification using smoke tests.

## Change Freeze

A change freeze applies for the 48 hours before and after major product releases and during the last 3 business days of each calendar quarter. Only Emergency changes are permitted during a freeze.

## Rollback

Every Standard and Significant change must have a documented rollback plan in the pull request description. For database schema migrations, a down-migration script must be tested and present in the PR.
