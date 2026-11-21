# Postmortem: INC-2031 — Payments API Complete Outage
**Date:** 2026-07-18  
**Severity:** SEV1  
**Duration:** 3 hours 12 minutes (11:23 – 14:35 UTC)  
**Authored by:** Alice Chen, Principal Engineer, Payments Platform  
**Reviewed by:** Eva Kowalski, Staff SRE; David Okonkwo, Customer Success EM  

---

## Executive Summary

On 18 July 2026, all payment charge and refund operations on the NovaEnterprise platform were unavailable for 3 hours and 12 minutes. The root cause was a silent, unannounced breaking change by our payment processor: they deprecated the `/v3/charge` endpoint and replaced it with `/v4/charge` without customer notification. Our integration library was pinned to v3 with no graceful fallback.

The estimated revenue impact is **$2.1M** in unprocessed transactions. Five enterprise customers — Meridian Financial Group, Apex Retail Corp, NovaTech Solutions, Sunrise Healthcare, and Coastal Logistics — escalated to executive support. All affected transactions were eventually processed in the recovery window between 15:00 and 16:30 UTC.

---

## Timeline

| Time (UTC) | Event |
|------------|-------|
| 11:23 | First 500 errors from `/api/payments/charge` detected by Datadog synthetic monitor |
| 11:25 | PagerDuty alert fires; Marcus Webb (on-call, Payments Platform) acknowledges |
| 11:28 | Marcus confirms 100% error rate on charge endpoint; declares SEV1; opens incident bridge |
| 11:35 | Alice Chen joins bridge; initial hypothesis is processor network issue |
| 11:42 | Processor status page checked — no active incidents listed |
| 11:50 | Marcus checks processor API changelog — discovers `/v3/charge` deprecated 2026-07-15 |
| 11:55 | Confirmed root cause: processor migrated to `/v4/charge`; v3 returns 410 Gone |
| 12:10 | Hotfix branch opened; Priya Desai begins migration to v4 client |
| 13:45 | Hotfix deployed to staging; contract tests pass against v4 sandbox |
| 14:20 | Hotfix deployed to production via fast-track (SRE approval, Alice Chen approval) |
| 14:35 | Error rate returns to 0%; all-clear declared |
| 15:00 | Recovery batch job begins reprocessing queued transactions |
| 16:30 | All queued transactions processed; customer communications sent |

---

## Root Cause Analysis

### Primary cause
The payment processor (undisclosed vendor, referred to as "the Processor") silently deprecated the `/v3/charge` REST endpoint and replaced it with `/v4/charge`. The migration window they offered to paying customers was 90 days per their contract, but the notification was sent only to the email alias on file, which had not been updated after a team reorganisation six months earlier. No technical notification (API header, error code, Processor Dashboard banner) was added to v3 responses before the deprecation deadline.

### Contributing factors
1. **No contract tests:** The Payments API integration had no automated Pact contract tests. A breaking change in the Processor's API was invisible until it reached production.
2. **No circuit-breaker:** When v3 returned `410 Gone`, the integration library retried up to 3 times before surfacing the error, adding latency and amplifying the blast.
3. **Stale notification alias:** The email alias `payments-vendor-alerts@novaenterprise.internal` was not monitored after the Q1 2026 team reorganisation.
4. **No canary deployment:** The integration library ships as a dependency bump; there was no canary deployment to catch the issue before 100% rollout.

---

## Impact

| Customer | Segment | Contract Tier | Impact |
|----------|---------|---------------|--------|
| Meridian Financial Group | Enterprise | Platinum | End-of-day reconciliation failed; 3 wire transfers delayed |
| Apex Retail Corp | Enterprise | Gold | Checkout flow down during peak hours; estimated $180K cart abandonment |
| NovaTech Solutions | Enterprise | Platinum | Subscription renewal batch failed; customer support volume +400% |
| Sunrise Healthcare | Mid-market | Silver | Staff payroll processing delayed |
| Coastal Logistics | Mid-market | Silver | Fuel card recharges failed; 12 drivers affected |

---

## What Went Well

- SEV1 declared within 5 minutes of first alert (SLA: 5 minutes) — ✅
- All-hands bridge assembled within 10 minutes — ✅
- Root cause identified within 30 minutes — ✅
- Hotfix deployed and confirmed within 3 hours of detection — within SEV1 MTTR target — ✅
- Recovery batch processed all queued transactions within 2 hours of resolution — ✅

---

## What Went Wrong

- Zero automated visibility into third-party API contract changes
- No graceful degradation when processor returns 4xx/5xx
- Notification alias not maintained after team reorganisation
- No change in runbook for handling processor endpoint deprecations

---

## Action Items

| # | Action | Owner | Due | ADR |
|---|--------|-------|-----|-----|
| 1 | Implement circuit-breaker for all processor calls | Alice Chen | 2026-08-15 | ADR-001 |
| 2 | Write Pact contract tests for all processor endpoints | Priya Desai | 2026-08-15 | ADR-002 |
| 3 | Audit and update all vendor notification aliases | Marcus Webb | 2026-07-25 | — |
| 4 | Add processor API changelog to weekly SRE review | Eva Kowalski | 2026-07-25 | — |
| 5 | Implement canary deployments for Tier-1 service dependencies | Eva Kowalski | 2026-09-30 | ADR-007 |

---

## Lessons Learned

1. **Vendor APIs are a dependency, not a contract.** We must treat third-party API integrations with the same rigour as internal APIs: contract tests, versioning, and change notifications.
2. **Fast failures are better than slow ones.** The 3-retry loop turned a 410 response into a ~9-second user-facing timeout. A circuit-breaker would have failed fast (< 50 ms) and allowed the UI to show a meaningful error.
3. **On-call handoff must include vendor alias review.** The stale alias was a process gap, not a tool gap. We are adding vendor alias review to the on-call handoff checklist.

---

## Follow-Up Review

Scheduled for 2026-08-05 to verify action items 1 and 2 are on track.
