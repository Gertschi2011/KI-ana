# Runbook: KiAnaDependencyDown

## Bedeutung

`KiAnaDependencyDown` bedeutet: die Backend-Instanz kann die Dependency **nicht erreichen** (z. B. `redis`, `qdrant`, `minio`).

## Sofort-Check (60 Sekunden)

- Grafana: Panel “Dependencies Up” + ggf. korrelierende Errors/5xx.
- Prometheus Quick Query:

```promql
ki_ana_dependency_up{dependency=~"redis|qdrant|minio"}
```

## Diagnose (5 Minuten)

1) Welche Dependency ist betroffen?

- In Alert/Labels: `dependency={{ $labels.dependency }}`

2) Container/Service Status prüfen:

- `docker compose -p ki_ana_staging -f docker-compose.staging.yml ps`

3) Logs der betroffenen Dependency:

- Redis: `docker compose -p ki_ana_staging -f docker-compose.staging.yml logs --tail=200 redis`
- Qdrant: `docker compose -p ki_ana_staging -f docker-compose.staging.yml logs --tail=200 qdrant`
- MinIO: `docker compose -p ki_ana_staging -f docker-compose.staging.yml logs --tail=200 minio`

## Sofortmaßnahmen

- Wenn nur eine Dependency betroffen ist: gezielt diese neu starten.

Beispiel:

- `docker compose -p ki_ana_staging -f docker-compose.staging.yml restart redis`

## Nachkontrolle

- `ki_ana_dependency_up{dependency="..."}` wieder `1`.
- Backlog/5xx/Task Failures normalisieren sich.
