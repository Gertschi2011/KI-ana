# 🗂️ KI_ana Adressbuch-System

**Version:** 1.0  
**Datum:** 29. Oktober 2025

---

## 📖 Zweck & Architektur

Das **Addressbook-Modul** erstellt automatisch einen hierarchischen Themenbaum aus allen Wissensblöcken von KI_ana. Dadurch kann sie:

- ✅ **Gezielt suchen** statt alle Blöcke zu scannen
- ✅ **Themenbereiche identifizieren** bevor sie nach Details sucht
- ✅ **Konflikte erkennen** zwischen verschiedenen Quellen
- ✅ **Wissenslücken finden** und durch Web-Suche ergänzen

### Architektur-Überblick

```
┌─────────────────┐
│ Memory Blocks   │
│ (JSON/JSONL)    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Indexer         │
│ (indexer.py)    │  ← Scannt Blocks, baut Baum
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ addressbook     │
│ .index.json     │  ← Generierter Index
└────────┬────────┘
         │
         ├─────────────┐
         ▼             ▼
┌──────────────┐  ┌──────────────┐
│ FastAPI      │  │ Frontend UI  │
│ Endpoints    │  │ (HTML/JS)    │
└──────────────┘  └──────────────┘
```

---

## 📊 Datenstruktur

### Block-Format (Eingabe)

Jeder Wissensblock sollte ein `topics_path` Feld haben:

```json
{
  "id": "block_12345",
  "title": "Die Machtergreifung",
  "topics_path": ["Geschichte", "Deutschland", "1933-1945"],
  "content": "...",
  "timestamp": 1698765432,
  "trust": 8
}
```

**Alternative Feld-Namen** (werden automatisch erkannt):
- `topics_path`, `topic_path`, `topics`, `topic`, `tags`

**Format-Optionen:**
- Liste: `["Geschichte", "Hitler"]`
- String mit Slash: `"Geschichte/Hitler"`
- Einzelner String: `"Geschichte"`

### Index-Format (Ausgabe)

```json
{
  "tree": {
    "name": "root",
    "path": [],
    "count": 3246,
    "children": [
      {
        "name": "Geschichte",
        "path": ["Geschichte"],
        "count": 2100,
        "blocks_count": 0,
        "children": [
          {
            "name": "Deutschland",
            "path": ["Geschichte", "Deutschland"],
            "count": 850,
            "blocks_count": 0,
            "children": [
              {
                "name": "1933-1945",
                "path": ["Geschichte", "Deutschland", "1933-1945"],
                "count": 450,
                "blocks_count": 450,
                "children": []
              }
            ]
          }
        ]
      }
    ]
  },
  "stats": {
    "total_blocks": 5000,
    "indexed_blocks": 3246,
    "topics": 187,
    "last_updated": 1698765432,
    "duration_ms": 1245
  },
  "version": "1.0"
}
```

---

## 🔌 API Endpoints

### GET `/api/addressbook/tree`

Gibt den kompletten Themenbaum zurück.

**Parameter:**
- `max_depth` (optional): Maximale Tiefe
- `include_blocks` (optional): Blocklisten einbeziehen

**Response:**
```json
{
  "ok": true,
  "tree": { ... },
  "stats": { ... }
}
```

### GET `/api/addressbook/list?path=Geschichte/Deutschland`

Listet alle Blöcke eines bestimmten Pfades.

**Parameter:**
- `path` (required): Themenpfad (z.B. "Geschichte/Hitler")
- `page` (optional): Seitenzahl (default: 1)
- `per_page` (optional): Items pro Seite (default: 50)
- `sort_by` (optional): Sortierfeld (timestamp, trust, title)
- `order` (optional): Sortierrichtung (asc, desc)

**Response:**
```json
{
  "ok": true,
  "path": ["Geschichte", "Deutschland"],
  "node": {
    "name": "Deutschland",
    "count": 850
  },
  "blocks": [...],
  "pagination": {
    "page": 1,
    "per_page": 50,
    "total": 850,
    "total_pages": 17
  }
}
```

### GET `/api/addressbook/search?q=hitler`

Fuzzy-Suche in Themennamen.

**Parameter:**
- `q` (required): Suchbegriff (min. 2 Zeichen)
- `limit` (optional): Max. Ergebnisse (default: 50)

**Response:**
```json
{
  "ok": true,
  "query": "hitler",
  "results": [
    {
      "name": "1933-1945",
      "path": ["Geschichte", "Deutschland", "1933-1945"],
      "count": 450,
      "blocks_count": 450
    }
  ],
  "count": 1
}
```

### POST `/api/addressbook/rebuild`

Baut den Index neu auf.

**Parameter:**
- `blocks_dir` (optional): Custom Blocks-Verzeichnis

**Response:**
```json
{
  "ok": true,
  "message": "Index rebuilt successfully",
  "stats": { ... }
}
```

### GET `/api/addressbook/stats`

Gibt Index-Statistiken zurück.

**Response:**
```json
{
  "ok": true,
  "stats": {
    "total_blocks": 5000,
    "indexed_blocks": 3246,
    "topics": 187,
    "last_updated": 1698765432
  },
  "version": "1.0"
}
```

---

## 🚀 Nutzung

### 1. Index erstellen

**CLI:**
```bash
python /home/kiana/ki_ana/tools/addressbook_indexer.py
```

**API:**
```bash
curl -X POST https://ki-ana.at/api/addressbook/rebuild
```

### 2. Baum anzeigen

**Browser:**
```
https://ki-ana.at/static/addressbook.html
```

**API:**
```bash
curl https://ki-ana.at/api/addressbook/tree
```

### 3. Suchen

**API:**
```bash
curl "https://ki-ana.at/api/addressbook/search?q=photosynthese"
```

---

## 🤖 Integration in KI_ana-Workflow

### Bevorzugte Such-Strategie

KI_ana sollte das Adressbuch nutzen, um:

#### **1. Themen identifizieren**
```python
# User fragt: "Was weißt du über Hitler?"

# Schritt 1: Adressbuch befragen
response = await fetch('/api/addressbook/search?q=hitler')
# → Findet: Geschichte/Deutschland/1933-1945 (450 Blöcke)

# Schritt 2: Gezielt diese Blöcke laden
blocks = await fetch('/api/addressbook/list?path=Geschichte/Deutschland/1933-1945')
# → Nur 450 Blöcke statt alle 7300!
```

#### **2. Wissenslücken erkennen**
```python
# User fragt: "Was ist Quantenverschränkung?"

# Schritt 1: Suche im Adressbuch
response = await fetch('/api/addressbook/search?q=quantenverschränkung')
# → Keine Ergebnisse!

# Schritt 2: Web-Suche aktivieren
web_results = await search_web("Quantenverschränkung")
# → Aktuelle Informationen holen

# Schritt 3: Neuen Block erstellen
# → Nächster Index-Lauf ordnet es unter Physik/Quantenmechanik ein
```

#### **3. Konflikte erkennen**
```python
# User fragt: "Wann starb Napoleon?"

# Adressbuch zeigt: Geschichte/Napoleon (23 Blöcke)
# → Lade alle 23 Blöcke
# → Finde widersprüchliche Daten
# → Gib Unsicherheit an: "Verschiedene Quellen nennen..."
```

### Auto-Trigger nach Block-Write

Nach jedem neuen Block sollte der Indexer getriggert werden:

```python
async def save_block(block: Dict[str, Any]):
    # Block speichern
    await write_block_to_file(block)
    
    # Index aktualisieren (async, non-blocking)
    asyncio.create_task(rebuild_addressbook_index())
```

**Optimierung:** Nur alle N Minuten oder nach X neuen Blöcken neu indexieren.

---

## 📈 Beispiel-Tree

```
root (7.300 Blöcke)
├── Geschichte (2.100)
│   ├── Deutschland (850)
│   │   ├── 1933-1945 (450)
│   │   ├── Nachkriegszeit (200)
│   │   └── DDR (200)
│   ├── Römisches Reich (600)
│   └── Mittelalter (450)
├── Wissenschaft (1.800)
│   ├── Physik (700)
│   │   ├── Quantenmechanik (200)
│   │   └── Relativität (150)
│   ├── Biologie (600)
│   │   ├── Evolution (180)
│   │   └── Genetik (220)
│   └── Chemie (500)
├── Technologie (1.500)
│   ├── KI & ML (400)
│   ├── Web-Entwicklung (350)
│   └── Datenbanken (250)
├── Philosophie (600)
└── Uncategorized (1.300)
```

---

## ⚡ Performance-Tipps

### Indexierung

- **Erste Indexierung:** ~2-5 Sekunden für 7.000 Blöcke
- **Inkrementelle Updates:** Geplant für v2.0
- **Memory Usage:** ~50MB für kompletten Baum

### Caching

Der Index wird als JSON-Datei gespeichert und muss nicht bei jedem Request neu gebaut werden.

**Cache-Invalidierung:**
- Nach jedem neuen Block (mit Delay)
- Manuell via `/api/addressbook/rebuild`

### Optimierung

Für sehr große Wissensbasen (>50.000 Blöcke):
- Nutze `max_depth` Parameter
- Implementiere lazy-loading von Unterbäumen
- Erwäge SQLite statt JSON

---

## 🔮 Roadmap (v2.0)

- [ ] **Inkrementelle Updates** (nur neue Blöcke indexieren)
- [ ] **Block-Visualisierung** (Graphenansicht)
- [ ] **Auto-Tagging** (KI schlägt topics_path vor)
- [ ] **Related Topics** (ähnliche Themenbereiche)
- [ ] **Timeline View** (chronologische Ansicht)
- [ ] **Export** (CSV, GraphML für Cytoscape)
- [ ] **Merge Detection** (doppelte Themen erkennen)

---

## 🐛 Troubleshooting

### Problem: "Index not found"

**Lösung:**
```bash
python tools/addressbook_indexer.py
```

### Problem: "Keine Themen angezeigt"

**Ursache:** Blöcke haben kein `topics_path` Feld

**Lösung:** Füge `topics_path` zu Blöcken hinzu oder nutze Auto-Tagging

### Problem: "Uncategorized zu groß"

**Ursache:** Viele Blöcke ohne Kategorisierung

**Lösung:** Batch-Update alter Blöcke mit topics_path

---

## 📝 Best Practices

### Block-Erstellung

**Gut:**
```json
{
  "topics_path": ["Wissenschaft", "Biologie", "Photosynthese"],
  "title": "Photosynthese-Prozess",
  ...
}
```

**Schlecht:**
```json
{
  "topic": "photosynthese",  // Zu flach!
  "title": "Photosynthese",
  ...
}
```

### Themen-Hierarchie

- **Max. 3-4 Ebenen** (zu tief = unübersichtlich)
- **Konsistente Namen** (z.B. immer "KI" nicht "KI", "Künstliche Intelligenz", "AI")
- **Deutsche Namen** (außer etablierte Fachbegriffe)
- **Singular** (z.B. "Datenbank" nicht "Datenbanken")

---

## 📚 Weitere Ressourcen

- **API-Docs:** `https://ki-ana.at/docs` (Swagger UI)
- **Source Code:** `/netapi/modules/addressbook/`
- **Frontend:** `/netapi/static/addressbook.html`

---

**Erstellt:** 29.10.2025  
**Version:** 1.0  
**Autor:** KI_ana Development Team
