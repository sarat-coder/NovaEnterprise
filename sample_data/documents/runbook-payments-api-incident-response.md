# Runbook: Payments API Incident Response

**Service:** Payments API  
**Team:** Payments Platform  
**On-call contact:** payments-oncall@novaenterprise.internal  
**Last updated:** 2026-10-01 (Alice Chen)  

---

## Overview

This runbook guides the on-call engineer through diagnosing and resolving incidents affecting the Payments API. The Payments API is a Tier-1 service; any degradation triggers a PagerDuty alert and may require a SEV1 or SEV2 declaration.

---

## Step 1: Confirm the incident

1. Check the Datadog dashboard: `Payments API — Live` (bookmark: `go/payments-dashboard`)
2. Confirm error rate by endpoint: `/v4/charge`, `/v4/refund`, `/v4/status`
3. Check the circuit-breaker state (from ADR-001): `kubectl get cm payments-circuit-state -n payments`
   - `OPEN` = processor is unreachable; fail-fast is active
   - `CLOSED` = processor is reachable; errors are application-level

---

## Step 2: Check the payment processor

1. Check the processor status page: `https://status.acmepayments.example`
2. Check the processor sandbox API: `curl https://sandbox.acmepayments.example/v4/health`
3. If the processor is down: open the incident bridge; declare SEV1; notify `#incidents` in Slack.

---

## Step 3: Diagnose application-level errors

If the processor is healthy, the problem is in our application.

1. Check pod logs: `kubectl logs -l app=payments-api -n payments --since=15m`
2. Check for recent deployments: `kubectl rollout history deployment/payments-api -n payments`
3. If a recent deployment is suspect: **rollback** using `kubectl rollout undo deployment/payments-api -n payments`

---

## Step 4: Network policy issues

Following INC-2036, check network connectivity if error type is `connection refused` or `connection timeout`:

1. Check egress policy: `kubectl get networkpolicy -n payments`
2. Test egress to processor IP: `kubectl exec -n payments <pod> -- curl -v https://api.acmepayments.example/v4/health`
3. If blocked: escalate to SRE on-call immediately. Do not modify network policy without SRE review.

---

## Step 5: Resolution and communication

1. Apply mitigation (rollback, circuit-breaker reset, network policy fix).
2. Confirm error rate returns to baseline.
3. Declare all-clear in `#incidents`.
4. For SEV1: draft customer notification within 2 hours. Use template: `go/payments-customer-notification`.
5. File postmortem within 5 business days.
