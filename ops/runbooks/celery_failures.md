# Runbook: KiAnaCeleryTaskFailureRateHigh

## Bedeutung

Dieser Alert signalisiert: erhöhte Task-Failures (Fehlerrate) über das Zeitfenster.

## Sofort-Check (60 Sekunden)

- Grafana Overview:
  - “Worker Failures (5m)”
  - “Task Volume” / “Task Failures” (falls vorhanden)
  - “Dependencies Up”

PromQL Quick Queries:

Failures by task:

```promql
sum(rate(ki_ana_celery_task_total{status="failure"}[10m])) by (task)
```

Failure rate by task:

```promql
sum(rate(ki_ana_celery_task_total{status="failure"}[10m])) by (task)
/
clamp_min(sum(rate(ki_ana_celery_task_total[10m])) by (task), 1)
```

## Diagnose (5 Minuten)

1) Betroffenen Task identifizieren (`task=...`).

2) Worker Logs prüfen:

- `docker compose -p ki_ana_staging -f docker-compose.staging.yml logs --tail=200 worker`

3) Dependency-Probleme ausschließen:

- `ki_ana_dependency_up{dependency=~"redis|qdrant|minio"}`

## Sofortmaßnahmen

- Wenn Worker “wedged”/reconnect loops: Worker restart:
  - `docker compose -p ki_ana_staging -f docker-compose.staging.yml restart worker`

- Wenn Dependency down: zuerst Dependency wiederherstellen (siehe Runbook `dependency_down.md`).

## Nachkontrolle

- Failure-rate sinkt.
- Backlog normalisiert sich.
