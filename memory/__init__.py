"""Memory package — four separated scopes (F15).

Scopes:
  organizational  shared company facts + fiscal calendar (read-only)
  conversation    per-session turns in Redis / fakeredis
  session         facts collected during one research run (DB)
  analyst         personal notes owned by an analyst (DB)
"""
