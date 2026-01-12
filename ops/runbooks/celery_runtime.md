# Runbook: KiAnaCelery*P95RuntimeHigh

## Bedeutung

Dieser Alert bedeutet: p95 Runtime eines kritischen Celery Tasks ist zu hoch (z. B. `embed.text` oder `ingest.parse_file`).

## Sofort-Check (60 Sekunden)

- Grafana Overview:
  - “Task Runtime p95”
  - “Backlog”
  - “Worker Failures (5m)”
  - “Dependencies Up”

PromQL Quick Queries:

p95 runtime by task:

```promql
histogram_quantile(
  0.95,
  sum(rate(ki_ana_celery_task_runtime_seconds_bucket[10m])) by (le, task)
)
```

Backlog:

```promql
ki_ana_celery_queue_backlog
```

## Diagnose (5 Minuten)

1) Worker logs prüfen (Errors/Timeouts/External API):

- `docker compose -p ki_ana_staging -f docker-compose.staging.yml logs --tail=200 worker`

2) Dependencies check:

- `ki_ana_dependency_up{dependency=~"redis|qdrant|minio"}`

3) Wenn backlog parallel steigt: möglicher Capacity issue → Worker skalieren oder Task optimieren.

## Sofortmaßnahmen

- Worker restart (wenn stuck):
  - `docker compose -p ki_ana_staging -f docker-compose.staging.yml restart worker`

- Wenn Dependency langsam/down: Dependency stabilisieren.

## Nachkontrolle

- p95 runtime fällt.
- Backlog fällt.
