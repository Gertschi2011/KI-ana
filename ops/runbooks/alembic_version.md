# Runbook: Alembic version_num VARCHAR

## Problem

Auf Postgres kann `alembic upgrade head` scheitern, wenn `alembic_version.version_num` nur `VARCHAR(32)` ist, aber die Revision-ID länger ist.

## Fix (safe, best-effort)

Einmalig auf der DB ausführen:

```sql
ALTER TABLE alembic_version
ALTER COLUMN version_num TYPE VARCHAR(255);
```

Warum das safe ist:

- In der Regel ist `alembic_version` nur 1 Zeile (oder wenige bei branches).
- Type-Erweiterung ist non-breaking.
- Keine App-Queries hängen an dieser Spalte.

## Hinweis

In KI_ana gibt es zusätzlich eine Alembic-Migration `0012a_alembic_ver_255`, die auf Postgres `alembic_version.version_num` auf `VARCHAR(255)` erweitert, bevor lange Revision-IDs gestempelt werden.
