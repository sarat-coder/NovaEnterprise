# Incident Response Policy

**Version:** 1.8  
**Effective date:** 2026-03-01  
**Owner:** SRE  
**Last reviewed:** 2026-09-01  

---

## Purpose

This policy defines the process for detecting, responding to, and learning from production incidents at NovaEnterprise.

## Severity Levels

| Severity | Definition | Response Time | Bridge Required |
|----------|-----------|---------------|----------------|
| SEV1 | Complete service outage, data loss, security breach, revenue > $500K/hour | 5 minutes | Yes |
| SEV2 | Significant degradation > 10% users, revenue $50K–$500K/hour | 15 minutes | Yes |
| SEV3 | Limited degradation, workaround available, revenue < $50K/hour | 60 minutes | No |

## Response Process

1. **Detect:** PagerDuty alert or customer report triggers an on-call notification.
2. **Acknowledge:** On-call engineer acknowledges within the response time SLA.
3. **Assess:** Determine severity within 5 minutes of acknowledgement.
4. **Declare:** For SEV1/SEV2, open incident bridge (Zoom link in PagerDuty). Declare severity in `#incidents` Slack channel.
5. **Investigate:** Follow the runbook for the affected service. Collect evidence (logs, metrics, traces).
6. **Mitigate:** Apply a mitigation (hotfix, rollback, feature flag, manual intervention).
7. **Resolve:** Confirm error rate is back to baseline. Declare all-clear in `#incidents`.
8. **Communicate:** Send customer notification for SEV1 within 2 hours of resolution.
9. **Review:** Postmortem drafted within 5 business days. Published to `#postmortems` and the internal knowledge base.

## On-Call Responsibilities

- Primary on-call responds within SLA.
- If not resolved within 30 minutes (SEV1) or 1 hour (SEV2), escalate to the secondary on-call.
- Engineering Manager is notified for all SEV1 incidents within 15 minutes of declaration.

## Postmortem Requirements

All SEV1 and SEV2 incidents require a written postmortem containing: timeline, root cause, impact, what went well, what went wrong, and action items with owners and due dates.

Postmortems are blameless. The goal is systemic learning, not individual accountability.
