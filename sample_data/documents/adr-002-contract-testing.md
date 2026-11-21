# ADR-002: Require Contract Testing for All Third-Party API Integrations

**Status:** Accepted  
**Date:** 2026-08-02  
**Authors:** Alice Chen, Priya Desai  
**Related incidents:** INC-2031

---

## Context

INC-2031 occurred because the payment processor changed their API contract (deprecated `/v3/charge`) without automated detection on our side. We rely on vendor email notifications and changelog subscriptions, both of which failed in this instance. We need a technical mechanism that surfaces breaking changes at development time, not production time.

## Decision

All third-party REST API integrations must have a **consumer-driven Pact contract test** that:

1. Defines the expected request/response shape from the consumer's perspective.
2. Is published to our internal **PactBroker** instance (hosted by SRE on the infra cluster).
3. Runs against the actual provider sandbox in CI on every pull request.

If the provider changes their API in a way that breaks the consumer contract, the CI pipeline fails and a Slack alert is sent to `#payments-platform` and the SRE on-call channel.

No integration with a third-party API may be deployed without a passing contract test against that provider's sandbox environment.

## Consequences

- CI time increases by 3–5 minutes per integration test.
- Requires PactBroker deployment and maintenance (SRE, assigned to Rahul Mehta).
- Teams must invest time writing and maintaining consumer contracts.
- Breaking API changes are surfaced at PR review time, not in production.
- This policy applies to: payment processor, SMS gateways, identity federation providers, and any new third-party API integration.
