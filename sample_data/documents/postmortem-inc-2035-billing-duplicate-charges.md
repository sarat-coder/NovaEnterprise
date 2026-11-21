# Postmortem: INC-2035 — Billing Engine Duplicate Charge Issue
**Date:** 2026-09-01  
**Severity:** SEV1  
**Duration:** ~4 hours 40 minutes (charge run at 00:10; discovered at 04:50 UTC)  
**Authored by:** Leo Santos, Staff Engineer, Payments Platform  
**Reviewed by:** Alice Chen; Eva Kowalski  

---

## Executive Summary

During the September 2026 billing cycle, 27 customers across all segments were charged twice for their monthly subscriptions. The root cause was a collision in the idempotency key generation algorithm: keys were derived from millisecond timestamps, and two retry attempts within the same millisecond produced identical keys, bypassing the payment processor's deduplication.

The issue was discovered 4 hours after the billing run when a customer contacted support. Total over-charge was approximately $84,000. All affected customers were refunded within 24 hours.

---

## Root Cause

The `BillingEngine.charge()` method generated idempotency keys using `str(int(time.time() * 1000))` — a 13-digit millisecond timestamp. Under the retry logic (up to 3 attempts, no delay), two attempts within the same millisecond produced identical keys. The payment processor's idempotency check accepted both, treating the second as a duplicate of a "new" key space (the processor resets idempotency per key after 24 hours).

## Impact

- 27 customers across enterprise (8), mid-market (12), and SMB (7) segments
- Total over-charge: ~$84,000
- 100% of affected customers refunded within 24 hours
- 3 enterprise customers escalated (Meridian Financial Group, NovaTech Solutions, Apex Retail Corp)

## Action Items

| # | Action | Owner | ADR |
|---|--------|-------|-----|
| 1 | Replace timestamp idempotency keys with UUID v7 | Leo Santos | ADR-003 |
| 2 | Add duplicate-charge detection alert (same amount, same customer, < 5 min) | Alice Chen | — |
| 3 | Build daily billing reconciliation report | Mia Johansson | — |
