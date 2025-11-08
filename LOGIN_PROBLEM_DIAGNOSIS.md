# 🔍 LOGIN PROBLEM - FINALE DIAGNOSE

## Problem:
Login schlägt fehl mit 401 Unauthorized

## Ursache gefunden:
Es starten sich **automatisch** immer wieder Backend-Prozesse!

### Prozesse die ich gefunden habe:
```
PID 69930 (kiana user) - manuell gestartet
PID 84814 (root) - automatisch gestartet
PID 89151 (root) - automatisch gestartet
```

→ **Es gibt einen systemd service oder cron der automatisch Backends startet!**

## 🔍 Was passiert:
1. Ich starte Backend mit korrekter DB (PostgreSQL)
2. Irgendein Service startet AUTOMATISCH ein weiteres Backend
3. Das automatische Backend nutzt vermutlich FALSCHE DB oder alte Config
4. Nginx leitet zu einem der beiden weiter (Random!)
5. Wenn es zum falschen leitet → 401 Fehler!

## 🔧 Lösung:
Wir müssen den automatischen Start-Service finden und deaktivieren!

### Mögliche Quellen:
- systemd service
- cron job
- supervisor
- docker container
- start_backend.sh wird irgendwo aufgerufen

## 📋 TODO:
1. Alle automatischen Starter finden
2. Diese deaktivieren
3. NUR EINEN Backend manuell starten
4. Login sollte dann funktionieren

---

**Das erklärt ALLES:**
- Warum Login manchmal funktioniert (wenn nginx zum richtigen Backend leitet)
- Warum Login meist nicht funktioniert (wenn nginx zum falschen leitet)
- Warum es immer wieder neue Prozesse gibt
