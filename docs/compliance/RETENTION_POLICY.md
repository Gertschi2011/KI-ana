# Retention Policy (Phase D1)

**Policy-ID:** `retention_policy_v1`

**Date:** 2026-01-12

Ziel: Verbindliche Aufbewahrungsfristen pro Datentyp (Minimierung + technische Löschbarkeit). Diese Policy wird in DSAR-Exports referenziert und durch einen Retention-Worker technisch durchgesetzt.

## Datentypen & Fristen

| Datentyp | Speicherort | Retention | Begründung |
|---|---|---:|---|
| Chat-Inhalte | DB (`conversations`, `messages`) | 30 Tage | Zweckbindung „Dialog“, kein Archiv |
| Learning-Candidates (pending/denied) | In-memory Store (best-effort) | 30 Tage | Minimierungsprinzip |
| Learning-Corrections (accepted) | Knowledge Blocks / Memory | dauerhaft* | Wissensbasis (anonymisiert) |
| Audit-Logs | DB (append-only) | 180 Tage | Rechenschaftspflicht |
| Login-/Security-Events | Audit | 180 Tage | Missbrauchsnachweis |
| DSAR-Exports | Temp-Files | 24h | Zweck erfüllt |
| Vektoren (Qdrant) | Qdrant | gekoppelt an Quelle | Quelle gelöscht → Vektor weg |
| Dateien (MinIO) | MinIO | gekoppelt an Quelle | kein „orphan storage“ |

\* dauerhaft = bis explizite Löschung oder Systemdekommissionierung.

## Enforcement (D2, technisch)

- Periodischer Retention-Job (z. B. täglich nachts) löscht hart nach Policy.
- Jede Löschung erzeugt ein Audit-Event (`DATA_DELETE` / `RETENTION_DELETE`).
- Cascade-Regeln bei User-Löschung: Chats + Candidates weg; Audit bleibt (pseudonymisiert).

### Implementation hooks

- Celery Task: `maintenance.retention_purge`
- Dry-run (optional, empfohlen beim ersten Rollout): `RETENTION_DRY_RUN=1`
- Parameter: `RETENTION_CHAT_DAYS=30`
