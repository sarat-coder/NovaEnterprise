-- Migration 001 — initial schema
-- Idempotent: uses CREATE TABLE IF NOT EXISTS.
-- Run against Postgres: psql $DATABASE_URL -f database/migrations/001_initial.sql
-- SQLite handled automatically by SQLAlchemy create_all() at startup.

\i database/schema.sql
