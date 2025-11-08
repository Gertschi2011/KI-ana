# 🔧 Quick Fixes Summary

## ✅ BEREITS GEFIXT:

### 1. Addressbook Tree
- **Problem:** API war unter `/api/memory` gemountet
- **Fix:** Router prefix `/api/addressbook` hinzugefügt
- **Status:** ✅ Funktioniert jetzt

### 2. Backend gestartet
- **Status:** ✅ Läuft auf Port 8000

---

## ⏳ NOCH ZU FIXEN:

### 3. User Creation API (500 Error)
**Problem:** Screenshot zeigt Fehler beim Anlegen neuer User
**Diagnose:** User-Model unterstützt alle Felder
**Mögliche Ursache:** 
- Fehlende Validierung
- Datenbank-Constraint
- Missing required field

**Fix-Approach:**
```python
# In /netapi/modules/admin/router.py
# Add better error handling and logging
# Ensure all required fields are set
```

### 4. Chat sagt "Llama" statt "KI_ana"  
**Problem:** Persona ist Llama, nicht KI_ana
**Diagnose:** Kein System-Prompt wird an Ollama gesendet
**Fix:** System-Prompt im `/api/chat/completions` Endpoint hinzufügen

**Lösung:**
```python
# Injiziere System-Prompt vor Forward zu Ollama
messages = body.get("messages", [])
if messages and messages[0].get("role") != "system":
    system_msg = {
        "role": "system",
        "content": "Du bist KI_ana, eine freundliche, neugierige und empathische KI-Assistentin..."
    }
    messages.insert(0, system_msg)
```

### 5. Navbar Design-Probleme
**Problem:** Nav bar hat Design-Issues in einigen Seiten
**Diagnose:** `styles.css` existiert, wird aber nicht überall korrekt geladen
**Fix:** Sicherstellen dass nav.html korrekt eingebunden ist

### 6. Live Logs
**Problem:** Live logs funktionieren nicht
**Diagnose:** Endpoint existiert vermutlich nicht oder SSE broken
**Fix:** SSE Endpoint prüfen und fixen

---

## 📝 Prioritäten:

1. **HOCH:** Chat-Persona (User-facing)
2. **HOCH:** User Creation (Admin-Feature blockiert)
3. **MITTEL:** Navbar Design
4. **NIEDRIG:** Live Logs
