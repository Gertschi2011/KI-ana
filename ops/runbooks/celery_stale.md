# Runbook: KiAnaCeleryAggStale (Backlog-gated)

## Bedeutung

Dieser Alert feuert nur, wenn:

- `time() - ki_ana_celery_agg_last_update_seconds{task=...}` über dem Schwellwert liegt **und**
- der Celery Backlog gleichzeitig über dem Threshold liegt

→ Also: Es staut sich Arbeit, aber die Worker-Aggregate werden nicht mehr aktualisiert (möglicher Worker-Hänger, Redis-Problem, Tasks stuck).

## Sofort-Check (60 Sekunden)

1) **Dashboard öffnen**

- Grafana → Overview → Panels:
   - “Agg Freshness Age (s)”
   - “Task Runtime p95”
   - “Worker Failures (5m)”
   - “Dependencies Up”
   - “Backlog”

2) **Prometheus Quick Queries**

- Backlog:
   - `ki_ana_celery_queue_backlog`
- Freshness Age:
   - `time() - ki_ana_celery_agg_last_update_seconds`
- Failures:
   - `sum(rate(ki_ana_celery_task_total{status="failure"}[10m])) by (task)`

## Diagnose (5 Minuten)

### A) Worker alive?

Auf dem Host:

- `docker compose -p ki_ana_staging -f docker-compose.staging.yml ps`
- `docker compose -p ki_ana_staging -f docker-compose.staging.yml logs --tail=200 worker`

Achte auf:

- Worker reconnect loops
- Exceptions bei Celery signals
- Redis connection errors / timeouts

### B) Redis erreichbar und stabil?

- `docker compose -p ki_ana_staging -f docker-compose.staging.yml logs --tail=200 redis`

### C) Backlog wächst, aber keine Runtime Updates?

Typische Ursachen:

- Worker hängt (CPU/RAM/Deadlock)
- Redis writes schlagen fehl → Freshness bleibt alt
- Task blockiert sehr lange (I/O, Netzwerk, External API) und verhindert Durchsatz

## Sofortmaßnahmen (mit niedrigerem Risiko beginnen)

1) **Worker Logs prüfen** → Ursache finden

2) **Worker soft restart**

- `docker compose -p ki_ana_staging -f docker-compose.staging.yml restart worker`

3) **Falls Redis das Problem ist**

- Redis restart (nur wenn keine Datenkorruption zu erwarten ist):
   - `docker compose -p ki_ana_staging -f docker-compose.staging.yml restart redis`

## Nachkontrolle

- Backlog fällt wieder?
- Freshness Age geht wieder runter?
- p95 Runtime normalisiert sich?
- Alert wird innerhalb weniger Minuten “inactive”.

## Notizen / Anpassungen

- Thresholds:
   - Backlog Gate: > 5 (Default)
   - Stale: > 15m, for 10m
- Wenn häufig “bursty” Betrieb: Backlog Gate erhöhen (z.B. 20) oder `for` verlängern.
