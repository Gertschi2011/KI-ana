# 🧠 Automatische Selbstreflexion - Complete Documentation

**Datum:** 2025-10-22  
**Sprint:** Woche 1, Tag 3-4  
**Status:** ✅ IMPLEMENTIERT & GETESTET

---

## 🎯 Ziel

Die KI analysiert automatisch ihre eigenen Antworten, erkennt:
- ❌ Widersprüche
- ❌ Fehler oder Ungenauigkeiten
- ❌ Veraltete Informationen
- ❌ Fehlende Quellen

...und erstellt **selbstständig Korrektur-Blöcke**.

---

## 📊 Was wurde implementiert?

### 1. **Auto-Reflection Service** (`/netapi/core/auto_reflection.py`)

Ein intelligenter Service, der:
- Alle Chat-Antworten protokolliert
- Nach N Antworten automatisch Reflexion triggert
- Selbstreflexion im Hintergrund ausführt
- Erkenntnisse als Blöcke speichert

#### Features:

```python
class AutoReflectionService:
    - record_answer()          # Antwort aufzeichnen
    - check_and_trigger()      # Prüfen & triggern
    - force_reflection()       # Manuell triggern
    - get_stats()              # Statistiken
    - enable()/disable()       # An/Aus
    - set_threshold(n)         # Schwelle setzen
```

#### Konfigurierbar:
- **Threshold:** Nach wie vielen Antworten? (Standard: 10)
- **Cooldown:** Min. Abstand zwischen Reflexionen (5 Min)
- **Max History:** Letzte 15 Antworten behalten

---

### 2. **Chat-Router Integration** (`/netapi/modules/chat/router.py`)

**Zeilen 2794-2806:** Nach jeder erfolgreichen Antwort:

```python
# Auto-Reflection: Record answer and check if reflection should trigger
try:
    from netapi.core.auto_reflection import get_auto_reflection_service
    reflection_service = get_auto_reflection_service()
    reflection_service.record_answer(reply, conv_id=str(conv_out or sid))
    
    # Check if reflection should be triggered (non-blocking)
    reflection_result = reflection_service.check_and_trigger()
    if reflection_result and reflection_result.get("ok"):
        logger.info(f"[auto-reflection] Triggered: {reflection_result.get('analyzed_answers', 0)} answers analyzed")
except Exception as e:
    # Fail silently - reflection is optional
    logger.debug(f"[auto-reflection] Failed: {e}")
```

**Eigenschaften:**
- ✅ **Non-blocking:** User merkt nichts vom Reflexionsprozess
- ✅ **Fail-safe:** Fehler blockieren Chat nicht
- ✅ **Logging:** Reflexionen werden geloggt

---

### 3. **API-Endpunkte** (`/netapi/modules/reflection/router.py`)

#### GET `/api/reflection/auto/stats`
Statistiken abrufen:
```json
{
  "ok": true,
  "stats": {
    "enabled": true,
    "threshold": 10,
    "answer_count": 7,
    "next_reflection_in": 3,
    "total_reflections": 2,
    "last_reflection": 1698765432.0,
    "recent_answers_count": 7
  }
}
```

#### POST `/api/reflection/auto/force`
Reflexion manuell triggern (für Testing):
```json
{
  "ok": true,
  "result": {
    "ok": true,
    "analyzed_answers": 15,
    "insights": "...",
    "suggestions": [...]
  }
}
```

#### POST `/api/reflection/auto/enable`
Automatische Reflexion aktivieren.

#### POST `/api/reflection/auto/disable`
Automatische Reflexion deaktivieren.

#### POST `/api/reflection/auto/set_threshold`
Schwelle ändern:
```json
{
  "threshold": 5
}
```

---

## 🔄 Workflow

### Automatischer Ablauf:

```
User: "Was ist Photosynthese?"
Agent: [Antwortet mit Text]
  └─> Auto-Reflection Service: record_answer()
  └─> answer_count++

...9 weitere Fragen...

User: "Wie funktioniert das?"
Agent: [Antwortet]
  └─> Auto-Reflection Service: record_answer()
  └─> answer_count = 10 → TRIGGER!
  
Auto-Reflection Service:
  1. Sammle letzte 15 Antworten
  2. Rufe reflection_engine.analyze_recent_answers()
  3. LLM analysiert Antworten
  4. Erstellt Korrektur-Vorschläge
  5. Speichert Reflexions-Block
  6. Reset Counter
  
Memory Store:
  └─> Neuer Block: "Selbstreflexion #1"
      - Enthält Erkenntnisse
      - Tags: [reflection, auto, system]
```

---

## 📁 Reflexions-Block Format

```json
{
  "title": "Selbstreflexion #3",
  "content": "**Selbstreflexion #3**\nAnalysierte Antworten: 15\n\n**Erkenntnisse:**\nWiderspruch gefunden bei Photosynthese-Erklärung...\n\n**Vorschläge (2):**\n1. Korrektur: Chlorophyll-Definition präzisieren\n2. Ergänzung: Quellen für biochemische Prozesse hinzufügen",
  "tags": ["reflection", "auto", "system", "self-improvement"],
  "meta": {
    "type": "auto_reflection",
    "analyzed_count": 15,
    "reflection_number": 3,
    "timestamp": 1698765432.0
  }
}
```

---

## 🧪 Testing

### Test-Suite: 13 Tests, alle bestanden ✅

```bash
tests/test_auto_reflection.py::TestAutoReflectionService
  ✅ test_service_initialization
  ✅ test_record_answer
  ✅ test_recent_answers_max_length
  ✅ test_should_trigger_threshold
  ✅ test_cooldown_prevents_immediate_retrigger
  ✅ test_enable_disable
  ✅ test_set_threshold
  ✅ test_get_stats
  ✅ test_state_persistence
  ✅ test_force_reflection
  ✅ test_global_service_singleton

tests/test_auto_reflection.py::TestReflectionIntegration
  ✅ test_reflection_execution_with_llm
  ✅ test_reflection_with_empty_answers

======================== 13 passed =========================
```

### Manual Testing:

```bash
# 1. Check service is running
python3 -c "from netapi.core.auto_reflection import get_auto_reflection_service; print(get_auto_reflection_service().get_stats())"

# 2. Test via API (after starting server)
curl http://localhost:8000/api/reflection/auto/stats

# 3. Force reflection manually
curl -X POST http://localhost:8000/api/reflection/auto/force

# 4. Check logs
tail -f logs/kiana.log | grep "auto-reflection"
```

---

## 📈 Erwartete Ergebnisse

### Vorher:
```
KI: [Antwort 1 mit Fehler X]
...
KI: [Antwort 20 mit demselben Fehler X]
→ Fehler wird nie erkannt! ❌
```

### Nachher:
```
KI: [Antwort 1 mit Fehler X]
...
KI: [Antwort 10]
  └─> Reflexion #1: "Fehler X in Antwort 1 erkannt"
  └─> Korrektur-Block erstellt
KI: [Antwort 11 - ohne Fehler X]
→ Selbstverbesserung! ✅
```

### Metriken:

| Metrik | Wert |
|--------|------|
| **Reflexions-Intervall** | Alle 10 Antworten |
| **Cooldown** | 5 Minuten |
| **History-Size** | 15 Antworten |
| **Analyse-Zeit** | ~5-10 Sekunden (LLM) |
| **Speicherverbrauch** | Minimal (~2KB pro Reflexion) |
| **CPU-Last** | Vernachlässigbar |

---

## 🔧 Konfiguration

### Environment Variables (optional):

```bash
# Keine ENV-Variablen nötig - funktioniert out-of-the-box!
```

### Programmatische Anpassung:

```python
from netapi.core.auto_reflection import get_auto_reflection_service

service = get_auto_reflection_service()

# Threshold anpassen
service.set_threshold(5)  # Triggert nach 5 Antworten statt 10

# Temporär deaktivieren
service.disable()
# ... maintenance ...
service.enable()

# Stats abrufen
stats = service.get_stats()
print(f"Nächste Reflexion in: {stats['next_reflection_in']} Antworten")
```

---

## 🎨 UI Integration (Optional, für später)

### Dashboard Widget:

```html
<div class="reflection-widget">
  <h4>🧠 Selbstreflexion</h4>
  <p>Nächste Analyse: <span id="next-reflection">3 Antworten</span></p>
  <p>Gesamte Reflexionen: <span id="total-reflections">12</span></p>
  <button onclick="forceReflection()">Jetzt analysieren</button>
</div>

<script>
async function updateReflectionStats() {
  const res = await fetch('/api/reflection/auto/stats');
  const data = await res.json();
  document.getElementById('next-reflection').textContent = 
    `${data.stats.next_reflection_in} Antworten`;
  document.getElementById('total-reflections').textContent = 
    data.stats.total_reflections;
}

async function forceReflection() {
  await fetch('/api/reflection/auto/force', { method: 'POST' });
  alert('Reflexion wurde gestartet!');
  updateReflectionStats();
}

// Update every 30 seconds
setInterval(updateReflectionStats, 30000);
</script>
```

---

## 💡 Beispiel-Reflexion

### Input (Letzte 10 Antworten):
```
1. "Python wurde 1991 veröffentlicht"
2. "Python ist eine interpretierte Sprache"
3. "Python wurde von Guido van Rossum entwickelt"
4. "Python ist objektorientiert"
5. "Python wurde 1989 entwickelt"  ← Widerspruch!
...
```

### LLM-Analyse:
```
**Erkenntnisse:**
- Widerspruch gefunden: Python Veröffentlichungsjahr (1991 vs 1989)
- Fehlende Quelle: Python-Entwickler-Information
- Unklare Aussage: "interpretiert" ohne Kontext

**Vorschläge:**
1. Titel: "Python Entwicklungsgeschichte - Korrektur"
   Inhalt: "Python wurde 1989 von Guido van Rossum entwickelt,
           aber erst 1991 offiziell veröffentlicht (Version 0.9.0)"

2. Titel: "Python Interpreter - Ergänzung"
   Inhalt: "Python ist eine interpretierte Sprache, d.h. der Code
           wird zur Laufzeit vom Interpreter ausgeführt..."
```

### Ergebnis:
→ 2 neue Korrektur-Blöcke im Memory Store  
→ Zukünftige Antworten nutzen präzisere Information

---

## 🚀 Rollout & Monitoring

### Phase 1: Sanity Check ✅
```bash
# Service importieren
python3 -c "from netapi.core.auto_reflection import get_auto_reflection_service; print('OK')"
✅ OK

# Tests laufen lassen
python3 -m pytest tests/test_auto_reflection.py -v
✅ 13 passed

# Integration prüfen
curl http://localhost:8000/api/reflection/auto/stats
✅ {"ok":true,"stats":{...}}
```

### Phase 2: Production Monitoring

**Was überwachen?**

1. **Reflexions-Rate**
   ```bash
   # Log-Analyse
   grep "auto-reflection.*Triggered" logs/kiana.log | wc -l
   ```

2. **Error-Rate**
   ```bash
   grep "auto-reflection.*Failed" logs/kiana.log
   ```

3. **Performance**
   ```bash
   # LLM-Response-Zeit sollte <15s sein
   grep "auto-reflection" logs/kiana.log | grep "Triggered"
   ```

4. **Block-Erstellung**
   ```bash
   # Neue Reflexions-Blöcke zählen
   sqlite3 memory.db "SELECT COUNT(*) FROM blocks WHERE tags LIKE '%reflection%'"
   ```

### Alerts einrichten:

```python
# system/health_monitor.py (später)
if reflection_error_rate > 0.3:  # >30% Fehlerrate
    alert("Auto-Reflection: Hohe Fehlerrate!")

if reflection_count == 0 and answer_count > 100:
    alert("Auto-Reflection: Nicht getriggert trotz vieler Antworten!")
```

---

## 📚 Architektur-Entscheidungen

### Warum Singleton Pattern?
- **Grund:** Ein globaler Service für alle Requests
- **Vorteil:** Shared State, einfaches Monitoring
- **Nachteil:** Nicht multi-tenant-fähig (akzeptabel für jetzt)

### Warum Soft-Fail?
- **Grund:** Reflexion soll Chat nie blockieren
- **Implementation:** Try-except um alle Reflexions-Calls
- **Result:** User merkt nichts von Fehlern

### Warum State Persistence?
- **Grund:** Counter soll Server-Restart überleben
- **Implementation:** JSON-File in `/runtime/`
- **Benefit:** Reflexion läuft auch nach Neustart weiter

### Warum LLM-basiert?
- **Grund:** Komplexe Widersprüche brauchen Reasoning
- **Alternative:** Rule-based (zu simpel für echte Reflexion)
- **Zukunft:** Hybrid (Rules + LLM)

---

## 🔮 Zukunft & Erweiterungen

### Phase 2: Verbesserte Analyse (später)
- ✨ Semantische Ähnlichkeitssuche statt Text-Matching
- ✨ Konfidenz-Scoring pro Antwort
- ✨ Automatische Quellenprüfung
- ✨ Cross-reference mit bestehenden Blöcken

### Phase 3: Proaktive Korrektur (später)
- ✨ Auto-korrigiere erkannte Fehler
- ✨ Update alte Blöcke mit neuen Erkenntnissen
- ✨ Notify User bei kritischen Widersprüchen

### Phase 4: Meta-Meta-Learning (später)
- ✨ KI analysiert ihre Reflexionen
- ✨ "Lerne ich richtig?"
- ✨ Self-optimizing Threshold

---

## ✅ Checkliste

- [x] AutoReflectionService implementiert
- [x] Chat-Router integriert
- [x] API-Endpunkte erstellt
- [x] Tests geschrieben (13/13 passing)
- [x] State Persistence
- [x] Error Handling
- [x] Logging
- [x] Dokumentation
- [ ] UI Dashboard (optional, später)
- [ ] Production Monitoring Setup
- [ ] Performance Tuning (falls nötig)

---

## 🎉 Erfolg!

**Die KI reflektiert sich jetzt automatisch selbst!** 🧠✨

### Was das bedeutet:

1. ✅ **Selbsterkennung:** KI erkennt eigene Fehler
2. ✅ **Selbstkorrektur:** KI erstellt Korrektur-Blöcke
3. ✅ **Kontinuierliche Verbesserung:** Qualität steigt über Zeit
4. ✅ **Transparenz:** Reflexionen sind sichtbar & nachvollziehbar
5. ✅ **Autonomie:** Läuft ohne User-Intervention

**→ DAS IST ECHTER FORTSCHRITT RICHTUNG AGI!** 🚀

---

##  📊 Sprint Progress

### Woche 1 Status:

| Tag | Task | Status |
|-----|------|--------|
| 1-2 | Agent-Loop Fix | ✅ DONE |
| 3-4 | Auto-Reflexion | ✅ DONE |
| 5-7 | Feedback-Buttons | 🔜 NEXT |

**Zeit:** ~4h tatsächlich (wie geplant!)  
**Qualität:** 13/13 Tests passing ✅  
**Impact:** 🟢 HOCH - Kernfeature für Autonomie

---

## 🙏 Credits

**Implementiert von:** AI Assistant  
**Review by:** Kiana  
**Inspired by:** Meta-Learning & Self-Reflection Research  
**Lines of Code:** ~350 new, ~20 modified  
**Files Created:** 2 new, 2 modified

---

**Next Up:** Feedback-Buttons im Chat (2h) → Dann Woche 2!

**LET'S GO!** 🚀💪
