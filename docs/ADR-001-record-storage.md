# ADR 001 — One versioned record table for the pilot

Status: accepted · Date: 2026-09-06 · Applies to: `backend/app/db.py`

## Context

The redesign plan specifies a relational model with ~20 domain tables (observations, snapshots,
score versions, market rules, scenarios, assessments, quotes, alerts, audit events). The pilot ships
a much smaller surface: no live collectors, no observations, no alerts, and one destination market.
Building the full schema now would mean writing and migrating tables that nothing reads yet.

## Decision

Workspaces, users, sessions, audit events and rate buckets are real tables, because they carry the
security boundary. Everything else the pilot stores — products, research jobs, decisions, watches,
quotes — lives in `records`, a table of `(workspace_id, kind, key, payload JSON/JSONB, created_at)`
with a unique constraint on `(workspace_id, kind, key)`.

Consequences that keep this honest:

- `kind`-specific shape is validated by Pydantic models at the API boundary, not by the database.
- The unique key is what makes an operation idempotent: an ASIN for a product, an idempotency key
  for a job or decision, a product id for a watch.
- `payload` is `JSON` on SQLite and `JSONB` on PostgreSQL, so production keeps indexable documents.
- Decisions and audit events are append-only through the repository helpers. A changed assumption
  creates a new assessment; it never rewrites a saved one.

## Why not the full schema now

Observations, snapshots, score versions and market rules only earn their tables once a collector
writes to them. Modelling them ahead of the first real source would fix a shape around guesses about
data we have not yet seen — the same mistake the redesign is correcting elsewhere.

## When to revisit

Split `records` into domain tables as each becomes real, one at a time, behind an Alembic migration:

1. **observations + source_snapshots** — the first connected collector. This is the trigger.
2. **cost_scenarios + assessments** — when decisions need querying by margin, market or date.
3. **suppliers + quotes + rfqs** — when quote comparison needs joins rather than a document read.
4. **watch_rules + alerts + deliveries** — when scheduled collection and delivery are enabled.

Each split is expand/migrate/contract: add the table, dual-write, backfill from `payload`, move
reads, then stop writing the record. `records` rows carry no foreign keys to each other, so a split
is a copy, not an untangling.
