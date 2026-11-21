# Postmortem: INC-2036 — Payments API Elevated Error Rate (Network Policy)
**Date:** 2026-09-19  
**Severity:** SEV2  
**Duration:** 28 minutes (15:03 – 15:31 UTC)  
**Authored by:** Marcus Webb, Senior Software Engineer, Payments Platform  
**Reviewed by:** Eva Kowalski; Alice Chen  

---

## Executive Summary

On 19 September 2026, approximately 22% of payment requests failed for 28 minutes after a Kubernetes network policy update accidentally blocked egress traffic to the payment processor's IP range. The change was applied directly to production without staging validation.

## Root Cause

A Kubernetes network policy was updated to restrict egress from the `payments` namespace. The CIDR block for the payment processor was accidentally omitted from the allowed egress rules. The change bypassed the standard change-review process because it was submitted as a "minor" policy cleanup.

## Impact

- ~22% of payment requests failed for 28 minutes
- Impacted customers: Meridian Financial Group, Apex Retail Corp, NovaTech Solutions, Pinnacle Media
- No revenue loss beyond delayed transactions (all retried successfully within 1 hour)

## Action Items

| # | Action | Owner | ADR |
|---|--------|-------|-----|
| 1 | Mandate change-review process for all network policy changes | Eva Kowalski | ADR-004 |
| 2 | Add network policy changes to change-freeze exceptions list | Sofia Andersen | ADR-004 |
| 3 | Write runbook for network policy validation in staging | Sofia Andersen | — |
