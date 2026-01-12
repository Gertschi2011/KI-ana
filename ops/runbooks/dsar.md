# DSAR (GDPR Export/Delete)

## Trigger / Wo ausgelöst

- Export: `POST /api/gdpr/export`
- Delete: `POST /api/gdpr/delete`

Beide Endpoints erzeugen Audit-Events in der Tabelle `audit_events`.

## Wo finden (DB Query)

Postgres Beispiel:

```sql
SELECT action,
       result,
       meta->>'dsar_id' AS dsar_id,
       ts
FROM audit_events
WHERE action LIKE 'DSAR_%'
ORDER BY ts DESC
LIMIT 50;
```

Typische Actions:

- `DSAR_EXPORT_REQUESTED`
- `DSAR_EXPORTED`
- `DSAR_DELETE_REQUESTED`
- `DSAR_DELETED`

## Was prüfen

- Pro Request eine `dsar_id` (UUIDv4) und konsistent über Requested/Result-Event.
- `retention_policy` im `meta` muss `retention_policy_v1` sein.
- `DSAR_EXPORTED`/`DSAR_DELETED` enthält `counts`.
- ZIP Export enthält `export_manifest.json`.
- `audit_events` ist **nicht** im Export enthalten (Manifest: `audit_excluded`).

## Minimaler E2E-Check

1) `POST /api/gdpr/export` auslösen und ZIP herunterladen.

2) ZIP prüfen:

- `export_manifest.json` vorhanden
- `retention_policy_v1` enthalten

3) DB prüfen:

- `SELECT ... WHERE action LIKE 'DSAR_%' ...` zeigt neue Events
