# Postmortem: INC-2010 — Identity Service Token Validation Failure
**Date:** 2026-01-14  
**Severity:** SEV1  
**Duration:** 47 minutes (09:12 – 09:59 UTC)  
**Authored by:** Bob Sharma, Engineering Manager, Identity  
**Reviewed by:** Eva Kowalski  

---

## Executive Summary

On 14 January 2026, JWT validation failed for approximately 35% of authentication requests for 47 minutes. The root cause was an automated certificate rotation script that added an already-expired TLS certificate to the rotation pool. The validation service loaded the expired certificate during a scheduled reload and began rejecting tokens signed with valid certificates.

## Root Cause

The `rotate-certs.sh` script downloaded a renewed certificate from the internal CA and copied it to the rotation pool without validating the expiry date. Due to a CA misconfiguration, the renewed certificate had already expired at issuance. The validation service loaded it on the next scheduled reload (every 10 minutes) and began rejecting all JWTs presented with the new certificate ID.

## Impact

- 35% of authentication requests returned 401 for 47 minutes
- 4 enterprise customers reported login failures (Meridian Financial Group, Apex Retail Corp, NovaTech Solutions, Sunrise Healthcare)
- Zero data loss; all sessions recovered after certificate reload

## Action Items

| # | Action | Owner | ADR |
|---|--------|-------|-----|
| 1 | Add pre-rotation expiry validation to rotate-certs.sh | Nina Petrov | ADR-005 |
| 2 | Deploy Prometheus cert-expiry exporter to all Tier-1 services | Rahul Mehta | ADR-005 |
| 3 | Alert at 30 days and 7 days before certificate expiry | Eva Kowalski | ADR-005 |
