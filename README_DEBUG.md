# KI_ana Debug / Web-Enricher

## Relevante Env Vars

- `KIANA_WEB_SEARCH_PROVIDER` (optional): Aktiver Provider (case-insensitive). Beispiel: `serper`.
- `WEB_SEARCH_PROVIDER_ORDER` (optional): Komma-separierte Provider-Reihenfolge (case-insensitive). Beispiel: `serper,duckduckgo-html`.
- `SERPER_API_KEY` (optional): Aktiviert Serper.
- `ALLOW_NET` / `KIANA_ALLOW_NET` (je nach Setup): muss aktiv sein, damit Webzugriffe erlaubt sind.

## Strukturierte Web-Enricher Logs

Beim Provider-Dispatch in `WebEnricher.web_search()` werden folgende Events geloggt:

- `web_enricher.provider_invoke`
- `web_enricher.provider_raw_count`
- `web_enricher.provider_annotated_count`
- `web_enricher.provider_success`
- `web_enricher.provider_fail`

## Debug Endpoints (Chat v2)

Prefix: `/api/v2/chat/debug/*`

- `GET /api/v2/chat/debug/web_status`
  - Liefert Provider-Konfiguration und ob `SERPER_API_KEY` gesetzt ist.
  - Ohne Login nur in `dev/test` (gesteuert über `KIANA_ENV` bzw. `PROMPT_DEBUG_PREVIEW`).

- `POST /api/v2/chat/debug/web_search`
  - Body: `{ "query": "…", "lang": "de", "max_results": 5 }`
  - Führt `WebEnricher.web_search()` aus und gibt normalisierte Result-Objekte zurück.
  - Ohne Login nur in `dev/test`.

- `POST /api/v2/chat/debug/prompt_preview`
  - Liefert zusätzlich `web_context_included` mit `{used, snippets, provider, reason}`.
  - Creator/Admin-only (ohne Login nur in `dev/test`).

## News-Intent Verhalten

Wenn die Pipeline `needs_current=True` setzt (News-Intent), dann:

- Web-Enrichment läuft zwingend (kein stilles Skipping).
- Wenn Web-Enrichment fehlschlägt oder keine Ergebnisse liefert, wird ein expliziter Hinweis-Block in den System-Prompt eingebettet.

## Memory Tool Endpoints

Zusätzlich existieren minimalistische Tool-Endpunkte:

- `POST /api/memory/search` (creator/admin)
  - Body: `{ "query": "…", "limit": 10 }`

- `POST /api/memory/store` (creator/admin)
  - Body: `{ "title": "…", "content": "…", "tags": ["…"], "url": "…" }`

## Smoke

- Lokal (Backend läuft bereits):
  - `make smoke`

- Mit Docker Compose (build + up):
  - `SMOKE_DOCKER=1 make smoke`

Hinweis: Für Debug-Endpunkte ohne Auth muss die App als `dev/test` laufen (z.B. `KIANA_ENV=dev` oder `PROMPT_DEBUG_PREVIEW=1`).

## Golden Docker Smoke (News Meta)

Ziel: Sicherstellen, dass der **Runtime-Pfad** (Docker Container) die News-Ranking-Pässe und die erweiterten `meta.web` Felder liefert (u.a. `relevance_applied`, `dedup_applied`, `service_penalty_applied`, `interest_used`, `penalized_examples`, `news_cards`) – und dass ein Signal (`/api/v2/chat/signal`) das Ranking sichtbar beeinflusst.

1) Backend neu bauen + neu erstellen:

- `docker compose up -d --build --force-recreate backend`

2) Debug-Request (News) absetzen:

- `docker compose exec -T backend curl -sS -X POST http://localhost:8000/api/v2/chat/debug/web_search -H 'Content-Type: application/json' -d '{"query":"Österreich Nachrichten","lang":"de","country":"AT","max_results":20,"mode":"news"}'`

3) Signal setzen (implizites Lernen):

- `docker compose exec -T backend curl -sS -X POST http://localhost:8000/api/v2/chat/signal -H 'Content-Type: application/json' -d '{"user_id":1,"country":"AT","lang":"de","mode":"news","signal_type":"open_source","url":"https://orf.at/","domain":"orf.at","category":"politik"}'`

4) Debug-Request erneut absetzen (News):

- `docker compose exec -T backend curl -sS -X POST http://localhost:8000/api/v2/chat/debug/web_search -H 'Content-Type: application/json' -d '{"query":"Österreich Nachrichten","lang":"de","country":"AT","max_results":20,"mode":"news","user_id":1}'`

5) Erwartete Signale (im JSON):

- Unter `meta.web`:
  - `used: true`
  - `relevance_applied: true`
  - `dedup_applied: true`
  - `service_penalty_applied: true` (alias: `penalty_applied: true`)
  - `penalized_examples` ist vorhanden (0–3 Beispiele)
  - `interest_used: true` (nach Signal)
  - `news_cards` ist vorhanden (typisch 5–7 Karten)
- Unter `meta.autonomy`:
  - `web_used: true`

Tipp (ohne `jq`):

- `... | python -c 'import sys,json; d=json.load(sys.stdin); w=(d.get("meta") or {}).get("web") or {}; print({k:w.get(k) for k in ["used","provider","relevance_applied","dedup_applied","penalty_applied"]}); print("news_cards_len=", len(w.get("news_cards") or []))'`

## Known issues (Full Suite)

Der komplette Test-Suite-Lauf ist in dieser Umgebung nicht zwingend grün, weil einige Teile bewusst optional/extern sind.

- Fehlende optionale Dependencies können Tests/Importe brechen (z.B. `sentence_transformers`, `numpy`).
- Manche Endpoints/Integrationen sind je nach Setup nicht aktiv (z.B. bestimmte Auth-/Audio-Routen).

Empfohlen für Phase 4:

- Phase4-Targeted Tests laufen (siehe `tests/test_*phase4*.py`)
- Golden Smoke (oben) im Docker-Runtime-Pfad ausführen
