# 🔧 KI_ana OS - Troubleshooting Guide

**Version:** 3.0  
**Letzte Aktualisierung:** 23. Oktober 2025

---

## 🚨 Häufige Probleme

### 1. Port 8000 already in use

**Problem:** Port 8000 ist bereits belegt

**Lösung:**
```bash
# Prozess finden
sudo lsof -i :8000

# Prozess beenden
kill -9 <PID>

# Oder anderen Port verwenden
P2P_PORT=8001 uvicorn netapi.app:app --port 8001
```

---

### 2. `psql: command not found`

**Problem:** `psql` ist am Host nicht installiert (Exit Code `127`).

**Lösung:** Verwende `psql` direkt im Docker-Container:

```bash
./scripts/psql.sh -c "SELECT 1;"
./scripts/pg_user_status.sh gerald
```

---

### 3. mDNS Discovery funktioniert nicht

**Problem:** Geräte finden sich nicht im LAN

**Lösung Linux:**
```bash
# Avahi installieren
sudo apt install avahi-daemon

# Avahi starten
sudo systemctl start avahi-daemon
sudo systemctl enable avahi-daemon

# Firewall öffnen
sudo ufw allow 5353/udp
```

**Lösung macOS:**
```bash
# Bonjour sollte standardmäßig laufen
# Testen mit:
dns-sd -B _kiana._tcp
```

**Lösung Windows:**
```bash
# Bonjour installieren (kommt mit iTunes)
# Oder: Bonjour Print Services
```

---

### 4. Import-Fehler / Module not found

**Problem:** Python-Module fehlen

**Lösung:**
```bash
# Virtual Environment aktivieren
cd ki_ana
source .venv/bin/activate

# Dependencies neu installieren
pip install --force-reinstall -r requirements.txt

# Spezifische Module
pip install sentence-transformers chromadb openai-whisper piper-tts
pip install zeroconf aiortc pynacl psutil
```

---

### 5. Permission denied (keys)

**Problem:** Keine Berechtigung für Private Keys

**Lösung:**
```bash
# Key-Permissions fixen
chmod 600 system/keys/*_private.key

# Owner prüfen
ls -la system/keys/

# Falls nötig, Owner ändern
chown $USER:$USER system/keys/*
```

---

### 6. WebRTC Connection failed

**Problem:** P2P-Verbindung schlägt fehl

**Diagnose:**
```bash
# NAT-Typ prüfen
curl https://api.ipify.org  # Public IP

# TURN Server testen
turnutils_uclient -t -u kiana -w password localhost
```

**Lösung:**
```bash
# TURN Server konfigurieren
# In .env:
TURN_SERVER=turn:your-server:3478
TURN_USERNAME=username
TURN_PASSWORD=password

# TURN Server starten
docker-compose -f infra/turn/docker-compose.turn.yml up -d
```

---

### 7. Backup schlägt fehl

**Problem:** Backup-Script funktioniert nicht

**Lösung:**
```bash
# Permissions prüfen
chmod +x scripts/backup.sh

# Backup-Verzeichnis erstellen
mkdir -p /backup/kiana

# Manuell ausführen
BACKUP_DIR=/backup/kiana ./scripts/backup.sh

# Logs prüfen
tail -f /var/log/kiana/backup.log
```

---

### 8. High CPU/Memory Usage

**Problem:** KI_ana verbraucht zu viel Ressourcen

**Diagnose:**
```bash
# Ressourcen-Nutzung prüfen
top -p $(pgrep -f uvicorn)

# Memory-Leak prüfen
python -m memory_profiler system/monitoring.py
```

**Lösung:**
```bash
# Worker reduzieren
uvicorn netapi.app:app --workers 1

# Memory-Limit setzen (Docker)
docker run --memory="2g" kiana-os

# Embeddings-Cache leeren
rm -rf data/chroma/*
```

---

### 8. Database locked

**Problem:** SQLite-Datenbank ist gesperrt

**Lösung:**
```bash
# Alle Prozesse stoppen
pkill -f uvicorn

# Lock-File löschen
rm data/kiana.db-wal
rm data/kiana.db-shm

# Datenbank-Integrität prüfen
sqlite3 data/kiana.db "PRAGMA integrity_check;"

# Neu starten
uvicorn netapi.app:app
```

---

### 9. Voice-Interface funktioniert nicht

**Problem:** Wake-Word Detection oder STT/TTS fehlerhaft

**Lösung:**
```bash
# PyAudio installieren
sudo apt install portaudio19-dev
pip install pyaudio

# Porcupine Access Key
# Registrieren auf: https://console.picovoice.ai/
# Key in .env: PORCUPINE_ACCESS_KEY=your-key

# Mikrofon testen
arecord -l  # Geräte auflisten
arecord -d 5 test.wav  # 5 Sekunden aufnehmen
aplay test.wav  # Abspielen

# Whisper-Modell neu laden
python -c "import whisper; whisper.load_model('base')"
```

---

### 10. CRDT State-Drift

**Problem:** Daten zwischen Geräten nicht synchron

**Diagnose:**
```bash
# CRDT-Health prüfen
curl http://localhost:8000/api/crdt/health

# Divergenz messen
python system/crdt_sync.py check
```

**Lösung:**
```bash
# Manual Sync
curl -X POST http://localhost:8000/api/crdt/sync

# Reset & Re-Sync
curl -X POST http://localhost:8000/api/crdt/reset

# Backup & Restore
./scripts/backup.sh
./scripts/restore.sh backup_name
```

---

## 🔍 Diagnose-Tools

### Health Check
```bash
curl http://localhost:8000/health
```

**Erwartete Ausgabe:**
```json
{
  "status": "healthy",
  "uptime": 3600,
  "cpu_percent": 25.5,
  "memory_percent": 45.2,
  "disk_percent": 18.6,
  "active_peers": 2,
  "blocks_count": 113
}
```

---

### Logs anzeigen
```bash
# Systemd Service
sudo journalctl -u kiana -f

# Docker
docker logs -f kiana-os

# Direkt
tail -f /var/log/kiana/app.log
```

---

### Network-Test
```bash
# Peers prüfen
curl http://localhost:8000/api/p2p/peers

# Discovery prüfen
curl http://localhost:8000/api/discovery/devices

# Messaging-Stats
curl http://localhost:8000/api/messaging/stats
```

---

### Performance-Profiling
```bash
# CPU-Profiling
python -m cProfile -o profile.stats netapi/app.py

# Memory-Profiling
python -m memory_profiler system/monitoring.py

# Network-Profiling
tcpdump -i any port 8000 -w capture.pcap
```

---

## 🚑 Emergency Procedures

### 1. System komplett zurücksetzen
```bash
# WARNUNG: Löscht alle Daten!

# Backup erstellen
./scripts/backup.sh

# Daten löschen
rm -rf data/*
rm -rf system/keys/*

# Neu initialisieren
python system/submind_manager.py init
```

---

### 2. Rollback zu vorheriger Version
```bash
# Backup wiederherstellen
./scripts/restore.sh backup_name

# Alte Version installieren
git checkout v2.0.0
pip install -r requirements.txt
```

---

### 3. Emergency Override aktivieren
```bash
# Not-Aus aktivieren
curl -X POST http://localhost:8000/api/emergency/override \
  -H "Authorization: Bearer $ADMIN_TOKEN"

# System stoppen
sudo systemctl stop kiana

# Logs prüfen
sudo journalctl -u kiana --since "10 minutes ago"
```

---

## 📊 Performance-Tuning

### Embeddings beschleunigen
```bash
# GPU verwenden (CUDA)
pip install sentence-transformers[cuda]

# Kleineres Modell
# In .env: EMBEDDING_MODEL=all-MiniLM-L6-v2
```

### Database optimieren
```bash
# SQLite optimieren
sqlite3 data/kiana.db "VACUUM;"
sqlite3 data/kiana.db "ANALYZE;"

# WAL-Mode aktivieren
sqlite3 data/kiana.db "PRAGMA journal_mode=WAL;"
```

### Network optimieren
```bash
# TCP-Tuning (Linux)
sudo sysctl -w net.core.rmem_max=26214400
sudo sysctl -w net.core.wmem_max=26214400

# WebRTC-Optimierung
# In .env: WEBRTC_MAX_BITRATE=2000000
```

---

## 🆘 Hilfe bekommen

### 1. Logs sammeln
```bash
# Diagnose-Paket erstellen
./scripts/collect-diagnostics.sh

# Enthält:
# - Logs
# - Config (ohne Secrets!)
# - System-Info
# - Network-Info
```

### 2. Issue erstellen
**GitHub:** https://github.com/your-org/ki_ana/issues

**Template:**
```markdown
**Problem:**
Kurze Beschreibung

**Schritte zur Reproduktion:**
1. ...
2. ...

**Erwartetes Verhalten:**
...

**Tatsächliches Verhalten:**
...

**System:**
- OS: Linux/macOS/Windows
- Version: 3.0.0
- Python: 3.10

**Logs:**
```
Relevante Logs hier
```
```

### 3. Community fragen
- **Discord:** https://discord.gg/kiana
- **Forum:** https://forum.kiana.ai
- **Email:** support@kiana.ai

---

**Letzte Aktualisierung:** 23. Oktober 2025  
**Version:** 3.0
