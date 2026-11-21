# ADR-003: Use UUID v7 for Idempotency Keys in Billing Engine

**Status:** Accepted  
**Date:** 2026-09-15  
**Authors:** Leo Santos, Alice Chen  
**Related incidents:** INC-2035

---

## Context

INC-2035 caused 27 customers to be charged twice because idempotency keys in the Billing Engine were generated from millisecond timestamps (`str(int(time.time() * 1000))`). Under rapid retries within the same millisecond, two calls produced identical keys. The payment processor's deduplication accepted both charges.

## Decision

Replace timestamp-based idempotency keys with **UUID version 7** (RFC 9562). UUID v7 provides:
- 48 bits of millisecond-precision time prefix (monotonically increasing for sortability)
- 74 bits of random suffix (probability of collision: 1 in 2^74 ≈ 1 in 10^22)

The Billing Engine `charge()` method must generate a new UUID v7 for **each retry attempt**. Idempotency keys are not reused between attempts.

The UUID v7 generator must use the `uuid7` Python library (or equivalent) and must not fall back to `uuid4` or timestamp-based schemes.

## Consequences

- UUID v7 keys are 36 characters (formatted with hyphens) vs 13-digit timestamps. Database index sizes increase marginally.
- Collision probability drops from approximately 1 in 1,000 (ms timestamp under load) to 1 in 10^22. Duplicate charges of this class become impossible.
- Idempotency keys are no longer human-readable timestamps; debugging requires joining on the charges table.
- The fix was implemented and deployed on 2026-09-20. INC-2035 is fully remediated.
