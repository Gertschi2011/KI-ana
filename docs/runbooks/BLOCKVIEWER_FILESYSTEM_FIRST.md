# Blockviewer — Filesystem-first runbook

Ziel: Der Blockviewer zeigt standardmäßig die tatsächlichen JSON-Dateien aus `memory/long_term/blocks` (und `system/chain`) an. Das Addressbook (`memory/index/addressbook.json`) dient als Index/Gruppe, kann aber neu aus den Dateien erzeugt werden.

Wichtige Endpunkte

- `GET /viewer/api/blocks?source=filesystem` — Liste aller Block-Dateien (default)
- `GET /viewer/api/blocks?source=addressbook` — Liste basierend auf `memory/index/addressbook.json`
- `GET /viewer/api/blocks/coverage` — Zählt FS-Dateien vs Addressbook-Einträge
- `GET /viewer/api/addressbook` — Addressbook als Baum (Kategorien → Topics → Block-IDs)
- `GET /viewer/api/addressbook/health` — Datei/Counts/letzter Rebuild
- `POST /viewer/api/rebuild-addressbook` — (creator/admin) Baut `memory/index/addressbook.json` aus Filesystem neu (liefert counts + took_ms)
- `GET /viewer/api/blocks/health` — Verifikation/Signer-Status

Schnelltests (lokal)

1) Syntax- und smoke-test (benötigt `requests`):

```bash
python3 netapi/tests/smoke_viewer.py --base http://127.0.0.1:8000
```

2) Coverage via curl (requires auth if server enforces it):

```bash
curl -b cookiejar.txt -c cookiejar.txt https://ki-ana.at/viewer/api/blocks/coverage
```

3) Rebuild addressbook (nur Creator/Admin):

```bash
curl -X POST -b cookiejar.txt -c cookiejar.txt https://ki-ana.at/viewer/api/rebuild-addressbook
```

Manuell aus Dateien neu bauen (alternativ zum HTTP-Endpoint)

```bash
python3 netapi/scripts/rebuild_addressbook.py
```

Fehlerbehebung

- 403 beim Rebuild: Prüfen, ob der aufrufende Benutzer die Rolle `creator` oder `admin` hat oder ob `PAPA_MODE` gesetzt ist.
- Ungleiche Counts: `fs_total` vs `addressbook_count` — falls Dateien fehlen, prüfe Dateiberechtigungen und Pfade (relativ zu PROJECT_ROOT).
- Server antwortet nicht: Prüfe, ob `uvicorn`/FastAPI läuft und ob Nginx Proxy zum richtigen Upstream zeigt (Next/Backend vs API).

Weiteres

- Tests: Runbook enthält `netapi/tests/smoke_viewer.py` für einfache Integrationschecks.
- Deployment: Nach Änderungen Backend neu starten / reload und ggf. `nginx -t && sudo systemctl reload nginx` ausführen.
