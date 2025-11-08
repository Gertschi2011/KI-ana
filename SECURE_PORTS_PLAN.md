# 🔒 PORT SECURITY PLAN

## Gefährliche offene Ports:

### ⚠️ KRITISCH (öffentlich erreichbar):
- **5432** - PostgreSQL (DB!) 
- **6333** - Qdrant Vector DB
- **3000** - Frontend (Docker)
- **8000** - Backend (sollte nur via nginx)
- **11434** - Ollama LLM

---

## PLAN:

### 1. Firewall aktivieren (SOFORT):
```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw --force enable
```

### 2. Docker-Ports auf localhost binden:
- PostgreSQL: 127.0.0.1:5432
- Qdrant: 127.0.0.1:6333  
- Frontend: 127.0.0.1:3000

### 3. Backend auf localhost:
- uvicorn --host 127.0.0.1

### 4. Ollama auf localhost:
- OLLAMA_HOST=127.0.0.1:11434

---

## Soll ich jetzt starten?
