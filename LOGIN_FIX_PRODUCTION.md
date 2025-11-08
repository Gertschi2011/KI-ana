# 🔧 Login-Problem auf ki-ana.at beheben

**Problem:** 401 Fehler beim Login auf ki-ana.at  
**Ursache:** Passwort auf Production-Server stimmt nicht überein  
**Lösung:** Passwort auf Production-Server zurücksetzen

---

## 🎯 Schnell-Lösung

### Auf dem Production-Server (ki-ana.at):

```bash
# 1. SSH zum Server
ssh user@ki-ana.at

# 2. Zum Projekt-Verzeichnis
cd /path/to/ki_ana

# 3. Passwort zurücksetzen
python3 reset_password.py gerald kiana

# 4. Testen
curl -X POST http://localhost:8000/api/login \
  -H "Content-Type: application/json" \
  -d '{"username":"gerald","password":"kiana"}'
```

---

## 📋 Detaillierte Anleitung

### Schritt 1: Auf Server einloggen

```bash
ssh user@ki-ana.at
# oder wie auch immer der Zugang ist
```

### Schritt 2: Script hochladen

**Option A: Über SCP (lokal ausführen):**
```bash
scp /home/kiana/ki_ana/reset_password.py user@ki-ana.at:/path/to/ki_ana/
```

**Option B: Direkt auf Server erstellen:**
```bash
# Das Script ist bereits in diesem Repo:
# /home/kiana/ki_ana/reset_password.py
# Einfach git pull auf dem Server
cd /path/to/ki_ana
git pull
```

### Schritt 3: Script ausführen

```bash
cd /path/to/ki_ana

# Erstmal User auflisten
python3 reset_password.py

# Passwort setzen
python3 reset_password.py gerald kiana
```

**Erwartete Ausgabe:**
```
============================================================
KI_ana Passwort-Reset Tool
============================================================

🔐 Passwort zurücksetzen für: gerald
   Neues Passwort: kiana

✅ User gefunden: gerald
   ID: 1
   Email: gerald.stiefsohn@gmx.at
   Role: owner
   Status: active

✅ Passwort erfolgreich zurückgesetzt!
   Username: gerald
   Neues Passwort: kiana

============================================================
✅ ERFOLGREICH
============================================================

Login-Daten:
  Username: gerald
  Passwort: kiana
```

### Schritt 4: Testen

**Auf dem Server:**
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"gerald","password":"kiana","remember":false}'
```

**Sollte zurückgeben:**
```json
{
  "ok": true,
  "token": "eyJ...",
  "user": {
    "id": 1,
    "username": "gerald",
    "role": "owner"
  }
}
```

### Schritt 5: Im Browser testen

1. Gehe zu: https://ki-ana.at/login
2. Username: `gerald`
3. Passwort: `kiana`
4. Login sollte funktionieren ✅

---

## 🔍 Troubleshooting

### Problem: "Command not found: python3"

```bash
# Versuche python statt python3
python reset_password.py gerald kiana
```

### Problem: "ModuleNotFoundError: No module named 'netapi'"

```bash
# Stelle sicher, dass du im richtigen Verzeichnis bist
cd /path/to/ki_ana

# Oder aktiviere virtual environment
source .venv/bin/activate
python3 reset_password.py gerald kiana
```

### Problem: "No such file or directory: reset_password.py"

```bash
# Git pull, falls Script noch nicht auf Server
git pull origin main

# Oder erstelle das Script manuell (siehe unten)
```

### Problem: Database nicht gefunden

```bash
# Prüfe .env Datei
cat .env | grep DATABASE

# Stelle sicher, dass DATABASE_URL korrekt ist
```

---

## 🚨 Alternative: Manuelles SQL-Update

Falls das Script nicht funktioniert, direkt über SQL:

```bash
# 1. Neuen Hash generieren (lokal)
python3 -c "
from netapi.modules.auth.crypto import hash_pw
print(hash_pw('kiana'))
"

# Output: $argon2id$v=19$m=65536,t=3,p=4$...

# 2. Auf Production-Server, in der Datenbank:
sqlite3 /path/to/kiana.db

UPDATE users 
SET password_hash = '$argon2id$v=19$m=65536,t=3,p=4$...' 
WHERE username = 'gerald';

.quit
```

---

## 📊 Wichtige Informationen

### Aktuelle Login-Daten (nach Reset)

```
Username: gerald
Email: gerald.stiefsohn@gmx.at
Passwort: kiana
Role: owner
```

### API-Endpoints die das Frontend verwendet

```
1. /api/login (primary)
2. /api/auth/login (fallback)
3. /api/me (session check)
4. /_/ping (health check)
```

### Warum 401 Fehler?

Der 401-Fehler ist **korrekt** wenn:
- Passwort falsch ist
- Username nicht existiert
- Account gesperrt ist

**Aktuell:** Passwort auf Production-Server stimmt nicht überein mit dem, was lokal gesetzt wurde.

---

## ✅ Checkliste

Auf dem Production-Server ausführen:

- [ ] SSH-Verbindung hergestellt
- [ ] Im richtigen Verzeichnis (`/path/to/ki_ana`)
- [ ] Script vorhanden (`reset_password.py`)
- [ ] Script ausgeführt (`python3 reset_password.py gerald kiana`)
- [ ] Erfolgsmeldung erhalten
- [ ] API-Test erfolgreich (curl)
- [ ] Browser-Login funktioniert

---

## 🔐 Nach erfolgreichem Login

**Passwort sofort ändern:**

1. Login mit: `gerald` / `kiana`
2. Gehe zu: Einstellungen
3. Ändere Passwort auf etwas Sicheres
4. Speichern

---

## 📞 Support

Falls Probleme auftreten:

1. **Logfiles prüfen:** `/var/log/kiana/` oder wo auch immer
2. **Server-Status:** `systemctl status kiana` (oder wie auch immer der Service heißt)
3. **Datenbank-Check:** `python3 reset_password.py` (ohne Argumente)

---

**Erstellt:** 2025-10-22 11:42  
**Für:** Production-Deployment auf ki-ana.at  
**Status:** Bereit zum Ausführen
