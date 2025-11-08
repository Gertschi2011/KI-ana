# 🚀 KI_ana Quick Start Guide

**Version:** 2.0  
**Datum:** 23. Oktober 2025

---

## 📋 System Requirements

### **Minimum:**
- CPU: 4 Cores
- RAM: 8GB
- Disk: 20GB
- OS: Linux, macOS, Windows (WSL2)
- Python: 3.10+

### **Recommended:**
- CPU: 8+ Cores
- RAM: 16GB+
- Disk: 50GB+ SSD
- GPU: Optional (für schnellere Embeddings)

---

## ⚡ Quick Install

### **One-Line Install (Linux/macOS):**
```bash
curl -sSL https://get.kiana.ai | bash
```

### **Manual Install:**
```bash
# Clone repository
git clone https://github.com/your-org/ki_ana.git
cd ki_ana

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install sentence-transformers chromadb openai-whisper piper-tts
pip install zeroconf aiortc pynacl psutil

# Create directories
mkdir -p data/chroma data/message_queue system/keys

# Copy configuration
cp .env.example .env
# Edit .env and set JWT_SECRET!

# Start KI_ana
uvicorn netapi.app:app --host 0.0.0.0 --port 8000
```

---

## 🎯 First Steps

### **1. Start KI_ana:**
```bash
cd ki_ana
source .venv/bin/activate
uvicorn netapi.app:app --host 0.0.0.0 --port 8000
```

### **2. Open Dashboard:**
```
http://localhost:8000/dashboard.html
```

### **3. Check Health:**
```bash
curl http://localhost:8000/health
```

---

## 🌐 Multi-Device Setup

### **Device A (Mother/Creator):**
```bash
# Start KI_ana
uvicorn netapi.app:app --host 0.0.0.0 --port 8000

# Device wird automatisch im LAN erkannt (mDNS)
```

### **Device B & C (Subminds):**
```bash
# Start KI_ana auf anderen Devices
uvicorn netapi.app:app --host 0.0.0.0 --port 8000

# Automatische Discovery & Connection
```

### **Verify Connection:**
```bash
# Check discovered devices
curl http://localhost:8000/api/discovery/devices

# Check connected peers
curl http://localhost:8000/api/p2p/peers
```

---

## 💬 Send Your First Message

### **Via API:**
```bash
curl -X POST http://localhost:8000/api/messaging/send \
  -H "Content-Type: application/json" \
  -d '{
    "recipient_id": "peer-device-id",
    "text": "Hello from KI_ana!",
    "metadata": {"priority": "high"}
  }'
```

### **Via Dashboard:**
1. Open Dashboard
2. Go to "Nachrichten" tab
3. Type message
4. Click "Senden"

---

## 📦 Create Your First Block

### **Via API:**
```bash
curl -X POST http://localhost:8000/api/blocks/create \
  -H "Content-Type: application/json" \
  -d '{
    "content": "My first knowledge block",
    "metadata": {"topic": "test", "tags": ["demo"]}
  }'
```

### **Via Dashboard:**
1. Open Dashboard
2. Go to "Wissens-Blöcke" tab
3. View synchronized blocks

---

## 🔧 Configuration

### **Essential Settings (.env):**
```bash
# Server Mode
SERVER_MODE=0  # 0=SQLite (default), 1=PostgreSQL

# P2P Network
P2P_PORT=8000
P2P_DISCOVERY=true

# Security
JWT_SECRET=your-secret-key-here  # ⚠️ CHANGE THIS!
ENCRYPTION_ENABLED=true

# Optional: TURN Server (for WAN)
TURN_SERVER=turn:your-server:3478
TURN_USERNAME=username
TURN_PASSWORD=password
```

---

## 🧪 Testing

### **Run Tests:**
```bash
# Phase 2 Integration Tests
python tests/test_integration_phase2.py

# P2P Messaging Tests
python tests/test_p2p_messaging.py

# Multi-Device Tests
python tests/test_multi_device_integration.py

# Extended Tests
python tests/test_extended_multi_device.py
```

---

## 🐳 Docker Deployment

### **Quick Start:**
```bash
docker-compose -f docker-compose.production.yml up -d
```

### **With TURN Server:**
```bash
# Start TURN
docker-compose -f infra/turn/docker-compose.turn.yml up -d

# Start KI_ana
docker-compose -f docker-compose.production.yml up -d
```

---

## 📊 Monitoring

### **Health Check:**
```bash
curl http://localhost:8000/health
```

### **Prometheus Metrics:**
```bash
curl http://localhost:8000/metrics
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

---

## 🔒 Security

### **Generate Secure JWT Secret:**
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### **Check Encryption Keys:**
```bash
ls -la system/keys/
# Should see *_private.key and *_public.key files
```

### **Firewall Setup:**
```bash
# Allow P2P port
sudo ufw allow 8000/tcp

# Allow mDNS
sudo ufw allow 5353/udp
```

---

## 🆘 Troubleshooting

### **Problem: Port already in use**
```bash
# Find process using port 8000
sudo lsof -i :8000

# Kill process
kill -9 <PID>
```

### **Problem: mDNS Discovery not working**
```bash
# Check Avahi (Linux)
sudo systemctl status avahi-daemon

# Check Bonjour (macOS)
dns-sd -B _kiana._tcp
```

### **Problem: Import errors**
```bash
# Reinstall dependencies
pip install --force-reinstall -r requirements.txt
```

### **Problem: Permission denied (keys)**
```bash
# Fix key permissions
chmod 600 system/keys/*_private.key
```

---

## 📚 Next Steps

### **Learn More:**
- [Deployment Guide](DEPLOYMENT_GUIDE.md)
- [Phase 4 Roadmap](PHASE4_ROADMAP.md)
- [API Documentation](API_DOCS.md)

### **Join Community:**
- GitHub: https://github.com/your-org/ki_ana
- Discord: https://discord.gg/kiana
- Forum: https://forum.kiana.ai

---

## 💡 Tips

### **Performance:**
- Use SSD for data directory
- Enable GPU for embeddings (if available)
- Increase RAM for large vector databases

### **Security:**
- Always use strong JWT_SECRET
- Enable HTTPS in production
- Rotate keys regularly (automatic after 30 days)

### **Networking:**
- Use TURN server for WAN connections
- Configure firewall properly
- Test with 3+ devices for best experience

---

## ✅ Checklist

- [ ] Python 3.10+ installed
- [ ] Dependencies installed
- [ ] .env configured (JWT_SECRET set!)
- [ ] KI_ana started
- [ ] Dashboard accessible
- [ ] Health check passes
- [ ] (Optional) Multi-device tested
- [ ] (Optional) Systemd service configured
- [ ] (Optional) Firewall configured
- [ ] (Optional) Backup configured

---

**Welcome to KI_ana 2.0!** 🤖🎉

**Need help?** Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md) or ask in the community!
