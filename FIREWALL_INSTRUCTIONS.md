# 🔒 FIREWALL SETUP

## Führe dieses Kommando aus:

```bash
sudo bash /home/kiana/ki_ana/setup_firewall.sh
```

**Dann Passwort eingeben und fertig!**

---

## Was passiert:

1. ✅ Eingehender Traffic: BLOCKED (außer 22, 80, 443)
2. ✅ Ausgehender Traffic: ERLAUBT
3. ✅ SSH (Port 22): OFFEN (für Admin-Zugriff)
4. ✅ HTTP (Port 80): OFFEN (für Website)
5. ✅ HTTPS (Port 443): OFFEN (für Website)
6. ❌ Alle anderen Ports: GESCHLOSSEN

---

## Danach sind geschützt:

- ❌ Port 3000 (Frontend) - NICHT MEHR ÖFFENTLICH
- ❌ Port 5432 (PostgreSQL) - NICHT MEHR ÖFFENTLICH  
- ❌ Port 6333 (Qdrant) - NICHT MEHR ÖFFENTLICH
- ❌ Port 8000 (Backend) - NICHT MEHR ÖFFENTLICH
- ❌ Port 11434 (Ollama) - NICHT MEHR ÖFFENTLICH

**Alle nur noch über nginx/localhost erreichbar!** ✅

---

## Sicherheit:

- ✅ Du kannst dich NICHT aussperren (SSH bleibt offen)
- ✅ Website funktioniert weiter (HTTP/HTTPS offen)
- ✅ Alle kritischen Dienste geschützt

**Führe das Script JETZT aus!** 🚀
