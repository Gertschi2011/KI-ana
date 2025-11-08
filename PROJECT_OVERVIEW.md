# KI_ana – Entwickler-Überblick, Status & Projekttree

Version: 2025-11-08  
Autor: Dev Overview Generator

## Zusammenfassung
- KI_ana ist ein modularer FastAPI‑Backend‑Dienst mit Chat/Knowledge‑Funktionalität, lokalem LLM, Web‑Recherche und Langzeitgedächtnis.
- Knowledge‑Pipeline: km → llm → web → child, mit persistenter Speicherung in Blöcken und Adressbuch.
- Adressbuch‑Kategorisierung und Rebuild-Routine vorhanden (Memory-Index + Baumstruktur).
- Logging konsolidiert auf einen FileHandler, doppelte Zeilen reduziert.

## Architektur
- **Backend**: FastAPI unter `netapi/`
- **Module**: `netapi/modules/*` (chat, memory, web, pages, etc.)
- **Core**: `netapi/core/*` (addressbook, reasoner, knowledge, state)
- **Speicher**:
  - Long‑Term Blöcke als JSON unter `memory/long_term/blocks/`
  - Indizes in `memory/index/` und `indexes/` (invertiert, Vektor, Meta)
  - SQLite `db.sqlite3` für strukturierte Tabellen (z. B. knowledge_blocks)
- **Frontend/UI**: `frontend/` und `netapi/static/` (Assets, Admin/Viewer)
- **Services/Tools**: `system/`, `tools/`, `scripts/`, `runtime/`

## Technologiestack
- Python 3.12, FastAPI, Uvicorn/Gunicorn
- SQLite (leichte Persistenz), JSON‑Dateien für Wissensblöcke
- Optional: Sentence‑Transformers (Embeddings)
- Lokales LLM (Ollama‑Integration, Reasoner‑Wrapper)
- Web‑Retriever (`web_qa.py`) für Quellen (z. B. Wikipedia)

## Knowledge‑Pipeline (Intent: knowledge_query)
- **km (Addressbook/KM zuerst)**
  - Prüft vorhandene Wissensblöcke zum Topic.
  - Hint‑Only‑Blöcke (z. B. „schau auf Wikipedia…“) werden erkannt und nicht direkt beantwortet.
  - Bei Faktenblock: Antwort direkt (ggf. paraphrasiert), Log: `selected=km`.
- **llm (zweiter Schritt)**
  - Wenn KM leer, lokales LLM generiert Erklärung.
  - Wenn ausreichend lang/zuverlässig: als Wissensblock speichern + im Addressbook registrieren, Log: `selected=llm`.
- **web (dritter Schritt)**
  - Nur bei unsicherem/zu kurzem LLM‑Ergebnis oder Hint‑Only‑KM.
  - Web‑Summary holen, kurz zusammenfassen, als Wissensblock speichern + registrieren, Log: `selected=web`.
- **child (letzter Schritt)**
  - Wenn alle anderen Wege keine brauchbare Antwort liefern oder explizite Lehr‑Trigger („Ich erklär’s dir“).
  - Nachfrage, Nutzerinput als Block speichern, Log: `selected=child`.
- In allen Fällen: `meta.pipeline` gesetzt, `state.last_pipeline` aktualisiert, Antwort über `_finalize_reply()`.

## Adressbuch & Kategorisierung
- Datei: `memory/index/addressbook.json`
- Inhalt: 
  - `tree`: Hierarchie `<Primärkategorie>/<Unterthema>/<Detail> -> [block_ids]`
  - `blocks`: flache Liste `{topic, block_id, path, source, timestamp, tags}`
- Automatischer Rebuild:  
  - `from netapi import memory_store as mem`  
  - `mem.rebuild_adressbuch()` oder `await mem.rebuild_adressbuch_async()`
- Heuristik:
  - Primärkategorien (~10): Allgemeinwissen, Biologie & Natur, Technik & Wissenschaft, Wirtschaft & Finanzen, Informatik & KI, Philosophie & Denken, Kommunikation & Sprache, Kunst & Kultur, Psychologie & Verhalten, Persönliche Themen.
  - Unterthemen aus Titel/Content‑Tokens.
  - Auto‑Tags (2–5) aus Kategorie/Subthemen/Token.
- Ziel: Antworten auf Themenabfragen („Was weißt du über Tiere?“) ohne Web.

## Logging
- Ein Root‑FileHandler (`/tmp/backend.log`), Child‑Logger ohne eigene Handler, `propagate=True`.
- Warnings mit Pfad: `knowledge_pipeline selected={km|llm|web|child} topic={...} user={...}`.
- Neustart empfohlen, damit die Handler‑Konfiguration aktiv wird.

## Projekttree (Auszug, relevante Verzeichnisse)
- **/home/kiana/ki_ana**
  - netapi/
    - app.py (Logger, App‑Setup)
    - core/ (addressbook.py, reasoner.py, knowledge.py, state.py, …)
    - modules/
      - chat/router.py (Knowledge‑Pipeline, Chat‑Endpoints)
      - memory/router.py (Memory‑APIs)
      - web/router.py (Web‑APIs)
      - … (auth, pages, viewer, etc.)
    - memory_store.py (Blöcke, Indizes, Adressbuch‑Rebuild)
    - web_qa.py (Web‑Retriever)
    - models.py, db.py (DB‑Modelle/Zugriff)
    - logging_bridge.py (Log‑Broadcast)
    - static/ (UI‑Assets)
  - memory/
    - long_term/blocks/*.json (Wissensblöcke)
    - index/addressbook.json, inverted.json, topics.json (Indizes)
  - db.sqlite3 (DB)
  - frontend/ (UI)
  - system/, tools/, scripts/, runtime/ (Dienste/Jobs)
  - tests/ (Tests)
  - docker‑/compose‑Dateien (Deployment)
  - viele Status- und Auditreports (*.md)

## Wichtige Module/Dateien (Funktionssicht)
- `netapi/modules/chat/router.py`  
  Knowledge‑Pipeline (km→llm→web→child), Hint‑Only‑Erkennung, State/Logging.
- `netapi/core/addressbook.py`  
  Topic‑Extraktion, Pfad‑Vorschläge, Addressbook‑Lookup, Registrierung.
- `netapi/memory_store.py`  
  Block‑CRUD, Indizes (invertiert, tf‑idf‑Vektor, Meta), Adressbuch‑Rebuild.
- `netapi/core/reasoner.py`  
  Wrapper um Planner/LLM (`deliberate_pipeline`), Unsicherheitschecks.
- `netapi/web_qa.py`  
  Web‑Retriever/QA, Quellenformatierung.
- `netapi/app.py`  
  FastAPI App, Logging‑Setup, Middlewares.

## API/Endpoints (Auswahl)
- Health/Status:
  - `GET /health`, `GET /_/ping`, `GET /api/metrics`, `GET /api/system/status`
- Chat:
  - `POST /api/chat` (Hauptroute)
  - `GET /api/chat/conv_state?conv_id=<id>`
- Memory/Addressbuch:
  - intern via `memory_store`/`addressbook` (manuell oder über Routermodule)

## Entwicklungs‑Workflows
- Setup:
  - Python venv, `pip install -r requirements.txt`
  - Start: `uvicorn netapi.app:app --host 0.0.0.0 --port 8000`
  - Docker: `docker-compose up -d` (siehe `docker-compose.yml`)
- Logs:
  - `/tmp/backend.log` (ein Handler)
- Knowledge‑Tests:
  - „Was ist ein Zebra?“ → LLM → Block speichern → beim nächsten Turn km.
  - „Was ist die Erde?“ → Hint‑Only? → Web → Summary‑Block → später km.
  - „Xorblax“ unbekannt → child → Nachfrage/Block speichern.

## Aktueller Status (Kernpunkte)
- Knowledge‑Pipeline in definierter Reihenfolge.
- Hint‑Only‑Blöcke werden nicht als Antwort genutzt; Web wird getriggert.
- LLM‑Antworten werden gespeichert und im Addressbook registriert.
- Adressbuch‑Rebuild implementiert (Kategorien/Tags/Baum).
- Logging‑Duplikate reduziert; TypeError (Planner kwargs) entfernt.

## Nächste Schritte (Empfehlungen)
- Dashboard:
  - „📚 Adressbuch“ (Baum + Blöcke/Kategorie)
  - „🧭 Letzter Denkpfad“ (meta.pipeline + Stimmung/Energie/Topics)
- Inkrementelles Adressbuch‑Update bei jedem neuen Block (statt Batch‑Rebuild).
- Optional: LLM‑gestützte Klassifizierung (genauere Unterthemen).
- E2E‑Tests für km→llm→web→child und Persistenzpfade.

---

Viel Erfolg beim Onboarding! Dieses Dokument kann direkt geteilt oder erweitert werden.
