# KI_ana – SLOs (M3)

Stand: 2026-01-11

Dieses Dokument definiert die initialen **SLIs** (was wir messen), **SLOs** (Zielwerte) und den **Error Budget** Rahmen.

## Messbasis (heute verfügbar)

Quelle: `GET /api/metrics` (Prometheus Text)

Aktuell nutzbare Metriken:

- `ki_ana_http_requests_total{route,method,status}`
- `ki_ana_http_request_duration_seconds_sum{route,method}`
- `ki_ana_http_request_duration_seconds_count{route,method}` (neu; erlaubt Avg)
- `ki_ana_process_uptime_seconds`
- `ki_ana_limits_exceeded_total{feature,scope}`

Hinweis:
- **p95/p99 direkt aus Prometheus** braucht Histogram-Buckets (`*_bucket`). Das ist als nächster Ausbau sinnvoll.
- Für das **Ops-Dashboard** können p95/p99 zusätzlich best-effort serverseitig aus einem Rolling-Window berechnet werden (nicht als Prometheus-SLI, aber UI/Sanity).

## Definitionen

Zeitfenster (Standard): **7 Tage** (rolling)

### Availability SLI

Für einen Endpoint $E$:

$$
SLI_{avail}(E) = \frac{\sum \text{2xx}(E)}{\sum \text{Requests}(E) - \sum \text{401}(E)}
$$

- **401 zählt nicht als Fehler** (wird aus dem Nenner ausgeschlossen)
- 5xx ist Fehler
- Timeouts zählen als Fehler, sobald wir sie als Status/Metric erfassen (später: explizite Timeout-Metrik)

### Latency SLI (Avg heute)

Für einen Endpoint $E$:

$$
SLI_{latency\_avg}(E) = \frac{\text{duration\_sum}(E)}{\text{duration\_count}(E)}
$$

- p95/p99 als Prometheus-SLI folgt mit Histogram.

## SLO Vorschlag (Phase M3)

### Chat v2

- **Availability SLO**: `POST /api/v2/chat` → **99.5% 2xx** (7d)
  - Error Budget: **0.5%** (7d)

- **Latency SLO (p95)**: `POST /api/v2/chat` → **p95 < 1.5s** (7d)
  - Messung:
    - kurzfristig: Ops-Rolling-Window (Sanity)
    - langfristig: Prometheus Histogram p95

### Auth

- `POST /api/login` → **2xx > 99.9%** (7d)
- `GET /api/auth/me` → **2xx > 99.9%** (7d)

### Learning (Consent)

- `POST /api/v2/learning/consent` → **2xx > 99.9%** (7d)

- **Backlog SLO (operational)**:
  - `pending_candidates <= 500` ODER
  - `oldest_pending_age_days < 30`

## Ops-Ampel (UI-Logik, nicht SLO)

Diese Ampel ist eine **Dashboard-Heuristik**:

- GREEN: 5xx_rate < 0.5% **und** p95(chat) < 1.5s
- YELLOW: 0.5–2% **oder** p95 1.5–3s
- RED: >2% **oder** p95 >3s **oder** db_ok=false
