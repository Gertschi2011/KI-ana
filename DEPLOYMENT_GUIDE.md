# 🚀 KI_ana Production Deployment Guide

**Version:** 1.0  
**Datum:** 23. Oktober 2025  
**Status:** Production-Ready

---

## 📋 Übersicht

KI_ana ist ein vollständig autonomes, offline-fähiges, P2P-enabled KI-System mit:
- 100% lokale AI (Embeddings, Voice, LLM)
- Dezentrales P2P-Netzwerk
- Blockchain-basierte Wissensverteilung
- Federated Learning
- E2E verschlüsselte Kommunikation

---

## 🎯 Deployment-Optionen

### **Option 1: Docker Compose (Empfohlen)** 🐳

**Vorteile:**
- Einfaches Setup
- Alle Services containerisiert
- Automatische Orchestrierung

**Start:**
```bash
cd /home/kiana/ki_ana
docker-compose -f docker-compose.production.yml up -d
```

**Services:**
- `kiana-backend` - FastAPI Backend (Port 8000)
- `qdrant` - Vector Database (Port 6333, optional)
- `ollama` - LLM Server (Port 11434)
- `nginx` - Reverse Proxy (Port 80/443, optional)

---

### **Option 2: Systemd Service** 🔧

**1. Service File erstellen:**
```bash
sudo nano /etc/systemd/system/kiana.service
```

```ini
[Unit]
Description=KI_ana P2P AI System
After=network.target

[Service]
Type=simple
User=kiana
WorkingDirectory=/home/kiana/ki_ana
Environment="PATH=/home/kiana/ki_ana/.venv/bin"
ExecStart=/home/kiana/ki_ana/.venv/bin/uvicorn netapi.app:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**2. Service aktivieren:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable kiana
sudo systemctl start kiana
sudo systemctl status kiana
```

---

### **Option 3: Standalone (Development)** 💻

**Start:**
```bash
cd /home/kiana/ki_ana
source .venv/bin/activate
uvicorn netapi.app:app --host 0.0.0.0 --port 8000 --reload
```

---

## 🔧 Konfiguration

### **Environment Variables** (`.env`)

```bash
# Server Mode
SERVER_MODE=0  # 0=SQLite, 1=PostgreSQL

# Vector Database
QDRANT_HOST=localhost
QDRANT_PORT=6333

# LLM
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama2

# P2P Network
P2P_PORT=8000
P2P_DISCOVERY=true

# Security
JWT_SECRET=your-secret-key-here
ENCRYPTION_ENABLED=true
```

---

## 📦 Abhängigkeiten

### **System Requirements:**
- Python 3.10+
- 8GB RAM (minimum)
- 20GB Disk Space
- Linux/macOS/Windows

### **Python Packages:**
```bash
pip install -r requirements.txt

# Phase 2 & 3 Dependencies
pip install sentence-transformers chromadb qdrant-client
pip install openai-whisper piper-tts
pip install zeroconf aiortc pynacl
```

### **External Services (Optional):**
- Qdrant (Vector DB) - Docker empfohlen
- Ollama (LLM) - Lokal installieren

---

## 🌐 Multi-Device Setup

### **Device A (Creator/Mother):**
```bash
# Start KI_ana
uvicorn netapi.app:app --host 0.0.0.0 --port 8000

# Device wird automatisch im LAN erkannt
```

### **Device B & C (Subminds):**
```bash
# Start KI_ana auf anderen Devices
uvicorn netapi.app:app --host 0.0.0.0 --port 8000

# Automatische Discovery via mDNS
# Automatische P2P Connection via WebRTC
```

### **Verify Connection:**
```bash
# Check discovered devices
curl http://localhost:8000/api/discovery/devices

# Check connected peers
curl http://localhost:8000/api/p2p/peers

# Send test message
curl -X POST http://localhost:8000/api/messaging/send \
  -H "Content-Type: application/json" \
  -d '{"recipient_id": "peer-uuid", "text": "Hello!"}'
```

---

## 🔒 Security

### **1. Firewall Setup:**
```bash
# Allow P2P port
sudo ufw allow 8000/tcp

# Allow mDNS
sudo ufw allow 5353/udp
```

### **2. SSL/TLS (Production):**
```bash
# Using Let's Encrypt
sudo certbot --nginx -d your-domain.com
```

### **3. Encryption Keys:**
```bash
# Keys werden automatisch generiert in:
/home/kiana/ki_ana/system/keys/

# Permissions prüfen
chmod 600 /home/kiana/ki_ana/system/keys/*_private.key
```

---

## 📊 Monitoring

### **Health Check:**
```bash
curl http://localhost:8000/health
```

### **Statistics:**
```bash
# System stats
curl http://localhost:8000/api/stats

# P2P stats
curl http://localhost:8000/api/p2p/stats

# Messaging stats
curl http://localhost:8000/api/messaging/stats

# Blockchain stats
curl http://localhost:8000/api/blockchain/stats
```

### **Logs:**
```bash
# Systemd
sudo journalctl -u kiana -f

# Docker
docker-compose logs -f kiana-backend
```

---

## 🔄 Backup & Recovery

### **Backup:**
```bash
#!/bin/bash
# backup.sh

BACKUP_DIR="/backup/kiana/$(date +%Y%m%d)"
mkdir -p $BACKUP_DIR

# Database
cp -r /home/kiana/ki_ana/data $BACKUP_DIR/

# Keys
cp -r /home/kiana/ki_ana/system/keys $BACKUP_DIR/

# Config
cp /home/kiana/ki_ana/.env $BACKUP_DIR/

echo "Backup complete: $BACKUP_DIR"
```

### **Recovery:**
```bash
#!/bin/bash
# restore.sh

BACKUP_DIR="/backup/kiana/20251023"

# Restore data
cp -r $BACKUP_DIR/data /home/kiana/ki_ana/

# Restore keys
cp -r $BACKUP_DIR/keys /home/kiana/ki_ana/system/

# Restore config
cp $BACKUP_DIR/.env /home/kiana/ki_ana/

echo "Restore complete"
```

---

## 🧪 Testing

### **Unit Tests:**
```bash
cd /home/kiana/ki_ana
source .venv/bin/activate

# Phase 2 Integration Tests
python tests/test_integration_phase2.py

# P2P Messaging Tests
python tests/test_p2p_messaging.py

# Multi-Device Tests
python tests/test_multi_device_integration.py
```

### **Load Testing:**
```bash
# Using Apache Bench
ab -n 1000 -c 10 http://localhost:8000/health

# Using wrk
wrk -t4 -c100 -d30s http://localhost:8000/api/stats
```

---

## 🚨 Troubleshooting

### **Problem: Service won't start**
```bash
# Check logs
sudo journalctl -u kiana -n 50

# Check port
sudo netstat -tulpn | grep 8000

# Check permissions
ls -la /home/kiana/ki_ana/data
```

### **Problem: P2P Discovery nicht funktioniert**
```bash
# Check mDNS
avahi-browse -a

# Check firewall
sudo ufw status

# Check network
ip addr show
```

### **Problem: Encryption Fehler**
```bash
# Regenerate keys
rm /home/kiana/ki_ana/system/keys/*_messaging_*.key

# Restart service
sudo systemctl restart kiana
```

---

## 📈 Performance Tuning

### **1. Database:**
```bash
# SQLite optimizations in hybrid_db.py
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA cache_size=10000;
```

### **2. Vector Search:**
```bash
# ChromaDB settings
CHROMA_BATCH_SIZE=100
CHROMA_CACHE_SIZE=1000
```

### **3. P2P:**
```bash
# Connection limits
MAX_PEERS=50
CONNECTION_TIMEOUT=30
```

---

## ✅ Production Checklist

- [ ] Environment variables konfiguriert
- [ ] SSL/TLS aktiviert (Production)
- [ ] Firewall konfiguriert
- [ ] Backup-Strategie implementiert
- [ ] Monitoring aktiviert
- [ ] Logs rotieren konfiguriert
- [ ] Health Checks funktionieren
- [ ] Multi-Device Tests bestanden
- [ ] Security Audit durchgeführt
- [ ] Dokumentation aktualisiert

---

## 📞 Support

**Dokumentation:**
- `README.md` - Übersicht
- `PHASE2_COMPLETE.md` - Phase 2 Features
- `PHASE3_WEEK1-10_PROGRESS.md` - Phase 3 Features
- `P2P_MESSAGING_SPRINT_REPORT.md` - Messaging

**Logs:**
- `/var/log/kiana/` - Application logs
- `journalctl -u kiana` - Systemd logs

---

**Deployment Guide Version:** 1.0  
**Erstellt:** 23. Oktober 2025  
**Status:** ✅ Production-Ready
