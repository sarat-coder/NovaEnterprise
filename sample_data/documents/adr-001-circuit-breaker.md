# ADR-001: Adopt Circuit-Breaker Pattern for Payment Processor Calls

**Status:** Accepted  
**Date:** 2026-08-02  
**Authors:** Alice Chen, Eva Kowalski  
**Related incidents:** INC-2031, INC-2026

---

## Context

Two incidents in Q2 and Q3 2026 (INC-2026, INC-2031) demonstrated that our Payments API has no graceful degradation path when the upstream payment processor is unavailable. When the processor returns errors or times out, our integration retries three times with no back-off, adding 9–27 seconds of latency per request and exhausting our connection pool, which amplifies the blast radius.

In INC-2031, a 410 Gone response from the deprecated v3 endpoint caused the entire Payments API to return 500 errors for over 3 hours. A circuit-breaker would have failed fast (< 50 ms) within seconds of the first failure.

## Decision

Implement a circuit-breaker around all payment processor HTTP calls using Resilience4j's `CircuitBreaker` decorator. The circuit has three states:

- **Closed (normal):** requests pass through; failure rate tracked in a sliding window of 20 calls.
- **Open (fail-fast):** triggered when failure rate exceeds 50% over the window. All calls immediately return a `PaymentProcessorUnavailableException`. Duration: 30 seconds before moving to half-open.
- **Half-open (probe):** 3 probe calls are allowed. If they succeed, the circuit closes. If they fail, it opens again.

When the circuit is open, the Payments API returns `HTTP 503 Service Unavailable` with a `Retry-After: 30` header. The Billing Engine must handle 503 as a retriable error and schedule a retry in the next billing job run.

## Consequences

- Payment failures become fast (< 50 ms) and explicit, rather than slow (up to 27 s) and ambiguous.
- Customers see a clear error message instead of a hanging request.
- Circuit-open events are alerted in PagerDuty (severity: SEV2 until resolved).
- Requires 2-week implementation sprint and load testing.
- Billing Engine must be updated to handle `503 + Retry-After` from Payments API.
