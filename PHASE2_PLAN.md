# 🚀 Phase 2: Lokale Autonomie - Arbeitsplan

**Zeitraum:** Q4 2025 - 3 Monate (Nov 2025 - Jan 2026)  
**Start:** 23. Oktober 2025  
**Ziel:** KI_ana läuft vollständig lokal ohne Server-Abhängigkeit

---

## 🎯 Phase 2 Hauptziele

Aus dem Fahrplan:
1. **Lokale AI-Modelle** - Keine Cloud-APIs mehr
2. **Submind-System** - Jedes Gerät wird eigenständig
3. **Offline-First Database** - SQLite statt PostgreSQL

---

## 📅 Wochenplan (12 Wochen)

### **Woche 1-2: Lokale Embeddings** 🔤
**Ziel:** Sentence-Transformers lokal statt OpenAI

**Tasks:**
- [ ] sentence-transformers installieren & testen
- [ ] Embedding-Service erstellen (`system/local_embeddings.py`)
- [ ] Qdrant mit lokalen Embeddings füttern
- [ ] Performance-Vergleich (OpenAI vs. lokal)
- [ ] Migration bestehender Embeddings

**Technologie:**
```python
from sentence_transformers import SentenceTransformer

# Modelle:
- all-MiniLM-L6-v2 (klein, schnell)
- all-mpnet-base-v2 (größer, besser)
- multilingual-e5-base (mehrsprachig)
```

**Erfolgskriterien:**
- ✅ Embeddings werden lokal generiert
- ✅ Keine OpenAI API Calls mehr
- ✅ Performance akzeptabel (<500ms)
- ✅ Qualität vergleichbar

---

### **Woche 3-4: Lokale TTS/STT** 🎤🔊
**Ziel:** Sprache ohne Cloud

**Tasks:**
- [ ] Whisper.cpp für STT integrieren
- [ ] Piper-TTS für TTS integrieren
- [ ] Audio-Pipeline erstellen
- [ ] Voice-Interface testen
- [ ] Latenz optimieren

**Technologie:**
```bash
# STT (Speech-to-Text)
whisper.cpp - Lokales Whisper-Modell
Modelle: tiny, base, small, medium

# TTS (Text-to-Speech)
piper-tts - Hochqualitative lokale TTS
Stimmen: de_DE, en_US, etc.
```

**Erfolgskriterien:**
- ✅ Voice Input funktioniert lokal
- ✅ Voice Output funktioniert lokal
- ✅ Latenz < 2 Sekunden
- ✅ Qualität gut genug für Alltagsnutzung

---

### **Woche 5-6: SQLite Migration** 💾
**Ziel:** Embedded Database statt PostgreSQL

**Tasks:**
- [ ] SQLAlchemy auf SQLite umstellen
- [ ] Migration-Script schreiben
- [ ] Daten von PostgreSQL zu SQLite migrieren
- [ ] Performance-Tests
- [ ] Fallback-Mechanismus (Hybrid-Mode)

**Technologie:**
```python
# Hybrid-Ansatz:
if os.getenv("SERVER_MODE") == "1":
    DATABASE_URL = "postgresql://..."
else:
    DATABASE_URL = "sqlite:///./kiana.db"
```

**Erfolgskriterien:**
- ✅ SQLite funktioniert als Drop-in Replacement
- ✅ Alle Features funktionieren
- ✅ Performance akzeptabel
- ✅ Migration ohne Datenverlust

---

### **Woche 7-8: ChromaDB Integration** 🔍
**Ziel:** Embedded Vector DB statt Qdrant

**Tasks:**
- [ ] ChromaDB installieren & testen
- [ ] Migration von Qdrant zu ChromaDB
- [ ] Embedding-Pipeline anpassen
- [ ] Search-Funktionalität testen
- [ ] Performance-Vergleich

**Technologie:**
```python
import chromadb

# Embedded Mode:
client = chromadb.Client()

# Persistent Mode:
client = chromadb.PersistentClient(path="./chroma_db")
```

**Erfolgskriterien:**
- ✅ ChromaDB läuft embedded
- ✅ Vector Search funktioniert
- ✅ Performance vergleichbar mit Qdrant
- ✅ Keine externen Dependencies

---

### **Woche 9-10: Submind-System** 🤖
**Ziel:** Device-Identität & Registrierung

**Tasks:**
- [ ] Device-ID Generierung (UUID)
- [ ] Submind-Registry erstellen
- [ ] Lokaler Memory pro Submind
- [ ] Submind-Rollen implementieren
- [ ] UI für Submind-Verwaltung

**Technologie:**
```python
# system/submind_manager.py
class Submind:
    id: str          # UUID
    name: str        # "Laptop", "Smartphone"
    role: str        # "primary", "secondary", "sensor"
    device_type: str # "desktop", "mobile", "iot"
    capabilities: List[str]
    
# Rollen (aus access_control.json):
- papa (Hauptsystem)
- creator (Entwickler-Zugriff)
- submind (Untergeordnetes System)
- sensor (Nur Daten sammeln)
```

**Erfolgskriterien:**
- ✅ Jedes Gerät hat eindeutige ID
- ✅ Subminds können sich registrieren
- ✅ Rollen-System funktioniert
- ✅ Lokaler Memory pro Submind

---

### **Woche 11-12: Integration & Testing** 🧪
**Ziel:** Alles zusammenführen & testen

**Tasks:**
- [ ] End-to-End Tests
- [ ] Performance-Optimierung
- [ ] Dokumentation schreiben
- [ ] Docker-Setup aktualisieren
- [ ] Deployment-Guide erstellen

**Tests:**
```bash
# Lokaler Modus (ohne Server):
- Embeddings generieren
- Voice Input/Output
- Vector Search
- Submind-Kommunikation
- Offline-Funktionalität

# Hybrid-Modus (mit Server):
- Sync zwischen Subminds
- Fallback auf Server
- Performance-Vergleich
```

**Erfolgskriterien:**
- ✅ Alle Features funktionieren lokal
- ✅ Keine Cloud-Dependencies mehr
- ✅ Performance akzeptabel
- ✅ Dokumentation vollständig

---

## 🛠️ Technologie-Stack (Phase 2)

### Neu hinzugefügt:
```
AI/ML:
├── sentence-transformers (Embeddings)
├── whisper.cpp (STT)
└── piper-tts (TTS)

Databases:
├── SQLite (User Data)
├── ChromaDB (Vector Search)
└── DiskCache (Caching)

Networking:
├── mDNS (Device Discovery)
└── WebRTC (P2P, später)
```

### Weiterhin verwendet:
```
Core:
├── FastAPI (Backend)
├── Ollama (LLM)
└── Python 3.11+

Frontend:
├── Static HTML/JS
└── TailwindCSS
```

---

## 📊 Metriken & KPIs

### Performance-Ziele:
- **Embedding Generation:** < 500ms pro Text
- **Voice-to-Text:** < 2s Latenz
- **Text-to-Voice:** < 1s Latenz
- **Vector Search:** < 100ms
- **Database Queries:** < 50ms

### Qualitäts-Ziele:
- **Embedding Quality:** > 85% Similarity zu OpenAI
- **STT Accuracy:** > 90% Word Error Rate
- **TTS Quality:** MOS > 4.0
- **System Uptime:** > 99%

### Resource-Ziele:
- **RAM Usage:** < 4GB (mit allen Modellen)
- **Disk Space:** < 10GB (Modelle + Data)
- **CPU Usage:** < 50% idle, < 80% peak
- **Startup Time:** < 30s

---

## 🚧 Risiken & Mitigationen

### Risiko 1: Performance
**Problem:** Lokale Modelle zu langsam  
**Mitigation:** 
- Quantisierte Modelle verwenden
- GPU-Acceleration (CUDA/Metal)
- Caching aggressiv nutzen

### Risiko 2: Modell-Größe
**Problem:** Modelle zu groß für Mobile  
**Mitigation:**
- Tiered Models (tiny/small/medium)
- On-Demand Download
- Model Pruning

### Risiko 3: Kompatibilität
**Problem:** Alte Features brechen  
**Mitigation:**
- Hybrid-Mode (Server + Lokal)
- Feature Flags
- Graduelle Migration

### Risiko 4: Komplexität
**Problem:** System wird zu komplex  
**Mitigation:**
- Modularer Aufbau
- Gute Dokumentation
- Automatisierte Tests

---

## 📝 Deliverables

### Code:
- [ ] `system/local_embeddings.py`
- [ ] `system/local_tts.py`
- [ ] `system/local_stt.py`
- [ ] `system/submind_manager.py`
- [ ] `system/hybrid_db.py`

### Dokumentation:
- [ ] `docs/LOCAL_SETUP.md`
- [ ] `docs/SUBMIND_GUIDE.md`
- [ ] `docs/MIGRATION_GUIDE.md`
- [ ] `docs/PERFORMANCE_TUNING.md`

### Tests:
- [ ] `tests/test_local_embeddings.py`
- [ ] `tests/test_local_voice.py`
- [ ] `tests/test_submind.py`
- [ ] `tests/test_offline_mode.py`

### Deployment:
- [ ] Docker-Compose Update
- [ ] Systemd Services Update
- [ ] Installation Script
- [ ] Migration Script

---

## 🎯 Definition of Done

Phase 2 ist abgeschlossen wenn:

1. ✅ **Lokale Modelle:**
   - Embeddings lokal generiert
   - TTS/STT funktioniert offline
   - Keine Cloud-API Calls mehr

2. ✅ **Submind-System:**
   - Device-Registrierung funktioniert
   - Rollen-System aktiv
   - Lokaler Memory pro Device

3. ✅ **Offline-First:**
   - SQLite als Primary DB
   - ChromaDB für Vectors
   - Volle Funktionalität ohne Internet

4. ✅ **Qualität:**
   - Alle Tests passing
   - Performance-Ziele erreicht
   - Dokumentation vollständig

5. ✅ **Deployment:**
   - Docker-Setup aktualisiert
   - Migration-Path dokumentiert
   - Production-Ready

---

## 🔄 Nächste Schritte (Heute)

### Sofort starten:
1. ✅ Phase 1 Review abgeschlossen
2. ⬜ sentence-transformers installieren
3. ⬜ Erste Embedding-Tests
4. ⬜ Performance-Baseline messen

### Diese Woche:
- Lokale Embeddings zum Laufen bringen
- Erste Integration mit Qdrant
- Performance-Vergleich dokumentieren

---

**Erstellt:** 23. Oktober 2025, 06:40 Uhr  
**Status:** 📋 Bereit zum Start  
**Nächstes Review:** 30. Oktober 2025 (Woche 1 Review)
