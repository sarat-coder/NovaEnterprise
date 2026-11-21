# Q3 2026 Quarterly Reliability Summary

**Period:** July 1 – September 30, 2026  
**Published:** 2026-10-10  
**Author:** Eva Kowalski, Staff SRE  

---

## Overview

Q3 2026 had four production incidents, including two SEV1s — the highest severity count since Q1 2025. Both SEV1s affected payment-related services. Total estimated revenue impact across all incidents: approximately $2.2M.

---

## Incident Summary

| ID | Date | Sev | Service | Duration | Revenue Impact | Customers |
|----|------|-----|---------|---------|----------------|-----------|
| INC-2031 | 2026-07-18 | SEV1 | Payments API | 3h 12m | ~$2.1M | 5 (3 enterprise) |
| INC-2033 | 2026-08-05 | SEV3 | Analytics Dashboard | 40m | Minimal | 3 |
| INC-2035 | 2026-09-01 | SEV1 | Billing Engine | 4h 40m* | ~$84K | 27 (over-charges) |
| INC-2036 | 2026-09-19 | SEV2 | Payments API | 28m | ~$0 (retriable) | 4 |

*Discovery-to-resolution time for INC-2035; charge errors occurred during the overnight billing run.

---

## Availability by Service (Tier-1)

| Service | SLA Target | Q3 Actual | Status |
|---------|-----------|-----------|--------|
| Payments API | 99.99% | 99.91% | ⚠️ BREACH |
| Identity Service | 99.99% | 99.99% | ✅ |
| Billing Engine | 99.99% | 99.95% | ⚠️ BREACH |

The Payments API and Billing Engine both breached their Q3 SLA. SLA credits have been issued to affected platinum and gold tier customers where contractually required.

---

## Customers Most Impacted

The following customers were impacted by multiple Q3 incidents:

| Customer | Incidents | Segment |
|----------|---------|---------|
| Meridian Financial Group | INC-2031, INC-2035 | Enterprise / Platinum |
| Apex Retail Corp | INC-2031, INC-2035 | Enterprise / Gold |
| NovaTech Solutions | INC-2031, INC-2035 | Enterprise / Platinum |
| Sunrise Healthcare | INC-2031, INC-2035 | Mid-market / Silver |
| Coastal Logistics | INC-2031, INC-2035 | Mid-market / Silver |

---

## ADRs Accepted in Q3

Three architectural decisions were accepted in response to Q3 incidents:

| ADR | Title | Status |
|-----|-------|--------|
| ADR-001 | Circuit-breaker for payment processor calls | In progress |
| ADR-002 | Contract testing for third-party API integrations | In progress |
| ADR-003 | UUID v7 for Billing Engine idempotency keys | Completed |
| ADR-004 | Network policy change-review process | Completed |

---

## Q4 Reliability Goals

1. Complete ADR-001 (circuit-breaker) before the November billing cycle.
2. First Pact contract test live in CI by end of October.
3. Canary deployment framework live for Payments API by end of November.
4. Zero SLA breaches in Q4.

---

## SLA Breach Notifications

SLA breach reports have been sent to:
- Meridian Financial Group (Platinum) — INC-2031 and INC-2035
- Apex Retail Corp (Gold) — INC-2031
- NovaTech Solutions (Platinum) — INC-2031 and INC-2035
