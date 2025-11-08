# DEV NOTES – KI_ana 2.0 (2025-11-08)

## Änderungen (inkrementell)
- Knowledge-Pipeline
  - Helper `_is_simple_knowledge_question` in `netapi/modules/chat/router.py` eingefügt.
  - LLM bevorzugt: Web-Fallback-Schwelle auf 0.35 gesenkt; Child-Mode bei einfachen Wissensfragen verhindert.
  - Quick-LLM-Pfad loggt jetzt `selected=llm` und setzt `pipeline="llm"`.
  - Zusätzliche Logs: `knowledge_pipeline: calling LLM quick…`, `… response chars=…`, sowie Selection-Logs für `llm` und `child`.
- Reasoner / LLM
  - `netapi/core/reasoner.py`: Robustes Logging rund um Planner-Call (vorher/nachher; Fehler mit Stacktrace).
  - Neuer direkter Ollama-Wrapper `call_llm(prompt)` mit httpx und Logging.
- App/Diagnose
  - `netapi/app.py`: Endpunkte hinzugefügt:
    - `GET /api/debug/ping` – prüft Logging.
    - `GET /api/llm/test` – testet Ollama via `reasoner.call_llm`.
- Memory/Viewer
  - `netapi/modules/memory/router.py`: `GET /api/memory/blocks` – minimaler Filesystem-Viewer der JSON-Blöcke.
  - Bestehender Knowledge-SQLite-Viewer bleibt unter `/api/memory/knowledge/*`.

## Tests / Quick-Checks
1) Backend neu starten (uvicorn/gunicorn/docker)
2) Logging
   - `curl -s http://localhost:8000/api/debug/ping` → `{ "ok": true }`
   - `tail -f /tmp/backend.log` und Aufruf wiederholen → `debug_ping called`
3) Ollama
   - Direkt: `curl http://localhost:11434/api/generate -d '{"model":"llama3.1","prompt":"Sag mir in einem Satz, was ein Zebra ist."}'`
   - Backend: `curl -s http://localhost:8000/api/llm/test` → Antworttext
4) Knowledge-Pipeline
   - Im Frontend/Chat „Was ist ein Zebra?“ → im Log:
     - `knowledge_pipeline: calling LLM quick...`
     - `LLM: sending prompt to Ollama...`
     - `knowledge_pipeline selected=llm topic=Zebra user=...`
5) Block-Viewer
   - `curl -s http://localhost:8000/api/memory/blocks` → Liste mit Items

## Bekannte offene Punkte
- JWT/Rollen: Struktur vorhanden (auth-router), aber keine neue Logik ergänzt.
- Dashboard/Papa-Tools: Viele Endpunkte vorhanden; ggf. UI-Anpassungen für Fallback-Werte nötig.
- Weitere Stabilisierung: Mehr Pipeline-Entry/Exit-Logs möglich (after_km/after_llm/after_web/after_child) falls nötig.

## Hinweise
- Log-File: `/tmp/backend.log` (Root-FileHandler). Keine doppelten Handler im Chat-Logger.
- Env für Ollama: `OLLAMA_BASE_URL` (Default `http://localhost:11434`), `OLLAMA_MODEL` (Default `llama3.1`).
