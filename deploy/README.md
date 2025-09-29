KI_ana Deploy Guide

This folder contains example configurations to run KI_ana as a systemd service
behind nginx with TLS, plus notes for chain synchronization across peers.

1) Systemd Service

- File: deploy/systemd/kiana.service
- Copy to: /etc/systemd/system/kiana.service
- Adjust paths if your project/user differs
- Reload and start:
  - sudo systemctl daemon-reload
  - sudo systemctl enable --now kiana
  - systemctl status kiana

2) nginx Server Block

- File: deploy/nginx/site.conf
- Copy to: /etc/nginx/sites-available/ki-ana.conf
- symlink to sites-enabled and reload nginx
  - sudo ln -s /etc/nginx/sites-available/ki-ana.conf /etc/nginx/sites-enabled/
  - sudo nginx -t && sudo systemctl reload nginx
- Replace <DOMAIN> and certificate paths for your host

3) Environment (.env)

- File: /home/kiana/ki_ana/.env
- Minimal suggested values:
  OLLAMA_HOST=http://127.0.0.1:11434
  OLLAMA_MODEL=llama3.1:8b
  ALLOW_NET=1
  CHAIN_APPEND=1

- Optional (recommended for UX/monetization & quotas):
  KI_UPGRADE_URL=https://ki-ana.at/abo
  FREE_DAILY_QUOTA=20

  Notes:
  - KI_UPGRADE_URL
    - Exposed via GET /api/system/config as `upgrade_url`
    - Used by frontend (static/chat.js) to link the 429 quota CTA to the upgrade page
    - Fallback if unset: /static/upgrade.html
  - FREE_DAILY_QUOTA
    - Read by backend (deps.DEFAULT_FREE_DAILY_QUOTA)
    - Enforced for free‐tier users when no per‑user `daily_quota` is set
    - Exposed via GET /api/system/config as `free_daily_quota`

4) Chain Sync

- Script: system/chain_sync.py
- Pull from remote peer via HTTP (uses the remote viewer API):
  python3 system/chain_sync.py pull --base https://peer.example.org
- Push via rsync (requires SSH/rsync):
  python3 system/chain_sync.py push --target user@host:/home/user/ki_ana/system/chain/

NOTE: The HTTP pull verifies block hashes and stores files under system/chain.


5) Troubleshooting

- Quota‑Pill zeigt "—" im Admin‑Dashboard
  - Prüfe, ob die API erreichbar ist: `GET /api/system/config`
  - Browser‑Konsole: Netzwerkfehler/CORS/Auth?
  - Dienst neu starten, falls `.env` Änderungen kürzlich erfolgt sind

- 429‑CTA im Chat verlinkt nicht korrekt
  - Prüfe `KI_UPGRADE_URL` in `.env` und ob `/api/system/config` die erwartete `upgrade_url` liefert
  - Fallback: Stelle sicher, dass `/static/upgrade.html` vorhanden ist

- Free‑Quota greift nicht
  - Nutzer könnte einen individuellen `daily_quota` gesetzt haben (via Rollen‑UI)
  - Globaler Default kommt aus `FREE_DAILY_QUOTA` (oder 20, wenn nicht gesetzt)
  - Stelle sicher, dass Rolle/Tier wirklich „user“ ist (Papa/Creator sind unbegrenzt)

6) Telemetry TTL‑Pruning (browser_errors)

- Script: `system/telemetry_prune.py` (löscht Einträge älter als 30 Tage; konfigurierbar via `--days` oder `KI_TELEMETRY_TTL_DAYS`)
- systemd Units (bereitgestellt):
  - `deploy/systemd/kiana-telemetry-prune.service`
  - `deploy/systemd/kiana-telemetry-prune.timer`

Installieren/Aktivieren:

```bash
sudo cp ki_ana/deploy/systemd/kiana-telemetry-prune.* /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now kiana-telemetry-prune.timer
```

Status prüfen:

```bash
systemctl list-timers | grep kiana-telemetry-prune
journalctl -u kiana-telemetry-prune.service -n 100 --no-pager
```

Manuell ausführen:

```bash
sudo systemctl start kiana-telemetry-prune.service
# oder:
python3 system/telemetry_prune.py --days 30
```

7) Alembic Migrations (DB Schema)

- Purpose: keep your database schema in sync with code (e.g., `browser_errors` table for telemetry)
- One-time init is already set up in this repo; run migrations on deploy or service start.

Run manually during deploy:

```bash
cd /home/kiana/ki_ana
# Activate venv if used
source .venv/bin/activate 2>/dev/null || true
alembic upgrade head
```

Example systemd ExecStartPre hook (recommended):

```
[Unit]
Description=KI_ana API
After=network.target

[Service]
User=kiana
WorkingDirectory=/home/kiana/ki_ana
EnvironmentFile=/home/kiana/ki_ana/.env
ExecStartPre=/bin/bash -c 'source /home/kiana/ki_ana/.venv/bin/activate 2>/dev/null || true; alembic upgrade head'
ExecStart=/bin/bash -c 'source /home/kiana/ki_ana/.venv/bin/activate 2>/dev/null || true; uvicorn netapi.app:app --host 0.0.0.0 --port 8000'
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Notes:
- The ExecStartPre runs `alembic upgrade head` for you before the API starts.
- If you don’t use a venv, drop the `source` parts.
- Ensure your `alembic.ini` is configured for your database DSN.

8) Device Provisioning & Tokens

- Devices (Papa OS, Bots) get a one-time plaintext token on create/rotate, only the hash is stored.
- Endpoints:
  - `POST /api/os/devices` → returns `{ id, token, token_hint }` once
  - `POST /api/os/devices/heartbeat` → requires `Authorization: Bearer <token>` (see localhost note)
  - `POST /api/os/devices/rotate` → issues new token (returned once)
  - `POST /api/os/devices/revoke` → revokes token immediately
  - `GET /api/os/devices` → lists devices with `token_hint`, `issued_at`, `last_auth_at`, `revoked_at` (no hashes)

Provisioning (Heartbeat) example:

```bash
curl -X POST https://<host>/api/os/devices/heartbeat \
     -H "Authorization: Bearer <token>" \
     -H "Content-Type: application/json" \
     -d '{"id": <device_id>, "status": "ok"}'
```

Require tokens even for localhost heartbeats (env)

```
# Default = 0 (localhost may post heartbeat without token)
# Production = 1 (enforce Bearer token even for localhost)
OS_DEVICES_LOCALHOST_REQUIRES_TOKEN=1
```

Notes:
- In development, localhost is allowed without token unless you set the env var above.
- In production, set `OS_DEVICES_LOCALHOST_REQUIRES_TOKEN=1` to enforce tokens everywhere.
- All device actions log Admin Audit entries (add/rotate/revoke/heartbeat).

9) Device Events Prune (TTL/Depth)

- Script: `system/device_events_prune.py`
- Purpose: clean up `device_events` by TTL and per-device max queue depth
- Env (in `.env`):
  - `KI_DEVICE_EVENTS_TTL_DAYS` (default 7)
  - `KI_DEVICE_EVENTS_MAX_DEPTH` (default 100)

Install systemd units:

```bash
sudo cp ki_ana/deploy/systemd/kiana-device-events-prune.* /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now kiana-device-events-prune.timer
```

Status / Logs:

```bash
systemctl list-timers | grep kiana-device-events-prune
journalctl -u kiana-device-events-prune.service -n 100 --no-pager
```

Manual run:

```bash
python3 system/device_events_prune.py --days 7 --max 100
```

10) Knowledge TTL‑Pruning (knowledge_blocks)

- Script: `system/knowledge_prune.py` (deletes Knowledge blocks older than TTL; default 365 days via `KI_KNOWLEDGE_TTL_DAYS` or `--days`)
- systemd Units (provided):
  - `deploy/systemd/kiana-knowledge-prune.service`
  - `deploy/systemd/kiana-knowledge-prune.timer`

Install/Enable:

```bash
sudo cp ki_ana/deploy/systemd/kiana-knowledge-prune.* /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now kiana-knowledge-prune.timer
```

Status:

```bash
systemctl list-timers | grep kiana-knowledge-prune
journalctl -u kiana-knowledge-prune.service -n 100 --no-pager
```

Manual run:

```bash
python3 system/knowledge_prune.py --days ${KI_KNOWLEDGE_TTL_DAYS:-365}
```

11) Planner Worker (Plans & Steps)

- API: `/api/plan` (create/list/get/cancel/retry), `/api/plan/lease-step`, `/api/plan/complete-step`
- Worker: `system/plan_worker.py` (polls API, executes simple step types)
- systemd Unit:
  - `deploy/systemd/kiana-plan-worker.service`

Install/Enable:

```bash
sudo cp ki_ana/deploy/systemd/kiana-plan-worker.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now kiana-plan-worker
```

Status / Logs:

```bash
systemctl status kiana-plan-worker
journalctl -u kiana-plan-worker -n 100 --no-pager
```

Env (optional):

```bash
# API Base (default http://127.0.0.1:8000)
PLANNER_API_BASE=http://127.0.0.1:8000
# Poll interval in seconds (default 2)
PLANNER_POLL_INTERVAL=2
# Use ADMIN_API_TOKEN for auth if present
ADMIN_API_TOKEN=...

12) Migrations (Alembic)

Use Alembic to apply schema changes (SQLite or Postgres). Run from the project root:

```bash
cd /home/kiana/ki_ana
# If alembic CLI is installed inside venv:
.venv/bin/alembic upgrade head
# Alternatively (no venv):
alembic upgrade head
```

Postgres vs. SQLite:

- Configure `DATABASE_URL` in `.env` (e.g., `postgresql+psycopg2://user:pass@host/dbname`).
- Adjust `alembic.ini` `sqlalchemy.url` or rely on env `DATABASE_URL`.
- Re-run `alembic upgrade head` after changing DB.

13) Shell Quick Guide (Knowledge+, Guardian, Autonomy‑Vorschläge)

Overview of the new Shell windows and how to use them efficiently.

- Knowledge+
  - Open: Topbar button "Wissen+" or Dock icon 📈 in `static/shell.html`.
  - Features:
    - Search input and Limit selector.
    - Time range filter: 24h, 7 Tage, 30 Tage, Alle (client-side filter).
    - Presets:
      - Tagesberichte → sets query to `tags:report,daily`, range 7d
      - Wochenberichte → sets query to `tags:report,weekly`, range 30d
      - Guardian → sets query to `tags:guardian,config,hash`, range 30d
    - Export: JSON, CSV of current results.
    - Charts:
      - Bar chart: count per day
      - Donut chart: distribution by `type`

- Guardian Feed
  - Open: Guardian window in `static/shell.html`.
  - Panels:
    - Config‑Änderungen (Knowledge tags: `guardian,config,hash`).
    - Validator‑Events (Knowledge tags: `guardian,validator`).
  - Sources:
    - Autonomy router action `config_hash_watch` writes to Knowledge when watched files change.
  - Configure watched files via ENV: `GUARDIAN_WATCH_FILES=/path/a.conf,/path/b.yaml`.

- Autonomy‑Vorschläge (Learning Autonomy)
  - Location: Autonomy window → panel "Vorschläge (Autonomy)".
  - Backend: Autonomy router cron `rule_suggestions` writes Knowledge with `type: suggestion`, `tags: autonomy,suggested_rule`.
  - Heuristics implemented:
    - 24h frequency: Device ≥3× offline in 24h → suggest device_offline reboot notification.
    - Time‑of‑day pattern (7d): Cluster by hour; if peak hour has ≥3 events and ≥50% of events → suggest scheduled restart HH:00.
  - UI actions:
    - Übernehmen: inserts a suggested rule into the Rules editor (remember to click "Save Rules").
    - Verwerfen: writes Knowledge `tags: autonomy,suggested_rule_dismissed` for future feedback loops.

Shortcuts & Tags

- Knowledge+ Presets
  - Tagesberichte → `tags:report,daily`
  - Wochenberichte → `tags:report,weekly`
  - Guardian → `tags:guardian,config,hash`

- Guardian Knowledge Tags
  - Config hash changes: `guardian,config,hash`
  - Validator events (if present): `guardian,validator`

Environment Variables

- `WORKER_CONCURRENCY`: number of worker threads processing steps.
- `LOW_PRIORITY_ALLOWED_HOURS`: window for low‑priority steps (e.g., `22-06`).
- `GUARDIAN_WATCH_FILES`: comma‑separated list of files for hash watchdog.

Developer Notes

- Code references:
  - Shell UI: `netapi/static/shell.html` (windows: knowledgeplus, guardian, autonomy suggestions panel)
  - Autonomy router: `netapi/modules/autonomy/router.py` (combo rules, daily/weekly reports, config hash watch, rule suggestions)
  - Worker: `system/plan_worker.py` (step types: web_fetch, analyze_knowledge; concurrency, priority, retry)

