# KI_ana 2.0 — JARVIS Backbone Builder

This is a production‑ready monorepo scaffold for KI_ana 2.0.

Quickstart:

1) Copy env
```
cp .env.example .env
```

2) Bring stack up
```
make up
```

3) Open apps
- Frontend: https://app.${DOMAIN_BASE}
- API: https://api.${DOMAIN_BASE}

See OPERATIONS.md, RUNBOOK.md, SECURITY.md for ops details.

## Status / Milestones

- Phase E → DONE (2026-01-12): Pro-Monitoring-Paket (SLIs/Alerts/Runbooks) — details in CHANGELOG.md
- Phase D → DONE (2026-01-12): Retention Policy v1 (30d Chat) + enforced purge + append-only `audit_events` + DSAR Export/Delete (`dsar_id`, `export_manifest.json`, audit excluded) — details in CHANGELOG.md and docs/compliance/RETENTION_POLICY.md
