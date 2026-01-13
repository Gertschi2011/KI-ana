# KI_ana Monitoring – Ops Checklist

## Ports / UIs

- Prometheus: `http://127.0.0.1:29090`
- Grafana: `http://127.0.0.1:23001` (admin / admin)
- Alertmanager: `http://127.0.0.1:29093`
- Quality Dashboard: Grafana → "KI_ana - Quality" (UID: `kiana-quality`)

## Quick Health Checks

- Backend metrics: `http://127.0.0.1:28000/api/metrics`
- Service health: `https://ki-ana.at/health` / `https://ki-ana.at/healthz`

## Reload: Prometheus Rules

Hinweis: Container hat kein curl → `wget` verwenden.

### Reload auslösen

```bash
docker compose -p ki_ana_monitoring -f monitoring/docker-compose.monitoring.yml exec -T prometheus \
  wget -qO- --post-data="" http://localhost:9090/-/reload >/dev/null && echo "reloaded"
```

### Regeln prüfen

- UI: Prometheus → Status → Rules
- API:

```bash
curl -sS -G "http://127.0.0.1:29090/api/v1/rules" | head
```

## Top PromQL Queries (Copy/Paste)

Traffic / Errors

Requests:

```promql
sum(rate(ki_ana_http_requests_total[5m]))
```

5xx rate:

```promql
sum(rate(ki_ana_http_requests_total{status=~"5.."}[5m])) / sum(rate(ki_ana_http_requests_total[5m]))
```

Latency (falls vorhanden)

p95 (Beispiel):

```promql
histogram_quantile(0.95, sum(rate(ki_ana_http_request_duration_seconds_bucket[10m])) by (le, route_group))
```

Dependencies

```promql
ki_ana_dependency_up
```

Down:

```promql
ki_ana_dependency_up == 0
```

Celery Worker SLIs

Task volume:

```promql
sum(increase(ki_ana_celery_task_total[5m])) by (task,status)
```

Failure rate:

```promql
sum(rate(ki_ana_celery_task_total{status="failure"}[10m])) by (task) / sum(rate(ki_ana_celery_task_total[10m])) by (task)
```

Runtime p95:

```promql
histogram_quantile(0.95, sum(rate(ki_ana_celery_task_runtime_seconds_bucket[10m])) by (le,task))
```

Freshness Age:

```promql
time() - ki_ana_celery_agg_last_update_seconds
```

Backlog (Name ggf. anpassen):

```promql
ki_ana_celery_queue_backlog
```

## What to do when alerts fire (short)

KiAnaDependencyDown

- Grafana “Dependencies Up” check
- Container logs: redis/qdrant/minio
- Restart only the affected dependency if needed

KiAnaCeleryTaskFailureRateHigh / RuntimeHigh

- Check worker logs
- Check Redis reachability
- Identify affected task(s) in “Task Volume” und “Runtime p95”
- Restart worker if stuck

KiAnaCeleryAggStale (backlog-gated)

- Runbook: `ops/runbooks/celery_stale.md`
