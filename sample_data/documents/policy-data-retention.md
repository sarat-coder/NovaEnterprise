# Data Retention Policy

**Version:** 2.3  
**Effective date:** 2026-01-01  
**Owner:** Legal & Compliance  
**Last reviewed:** 2026-06-15  

---

## Purpose

This policy defines how long NovaEnterprise retains data in its systems of record. All engineering teams are responsible for ensuring their services comply.

## Retention Periods

| Data Category | Retention Period | Legal Basis |
|---------------|-----------------|-------------|
| Customer PII (name, email, address) | 7 years from contract end | GDPR Art. 17; contractual obligation |
| Payment transaction records | 7 years from transaction date | PCI-DSS Requirement 10 |
| Audit logs (admin actions, auth events) | 5 years | Regulatory requirement |
| Incident records (postmortems, timelines) | 5 years | Internal SLA; legal discovery |
| Research sessions (AI assistant output) | 90 days | Privacy by default |
| Uploaded documents (internal knowledge base) | Until explicitly deleted by admin | Operational |
| Employee records | 7 years from employment end | Employment law |
| Support tickets | 3 years from closure | Customer SLA |

## Deletion Process

Data past its retention period must be deleted or anonymised within 30 days of the retention period expiry. Deletion requests from customers under GDPR Art. 17 must be completed within 30 days of receipt.

All deletions affecting more than 1,000 records must be approved by the Legal team before execution.

## Exceptions

Exceptions to this policy require written approval from the Chief Legal Officer. All exceptions are logged in the Legal exception register.

## Compliance

The Data Platform team runs quarterly automated retention scans. Non-compliant data is flagged in the Data Governance dashboard. Engineering teams have 30 days to remediate flagged findings.
