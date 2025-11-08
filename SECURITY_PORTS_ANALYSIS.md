# 🔒 SECURITY ANALYSE - Offene Ports

**Datum:** 2025-11-03 11:48 UTC+01:00  
**Status:** ⚠️ **KRITISCH - FIREWALL IST INAKTIV!**

---

## ⚠️ HAUPTPROBLEM:

```
ufw status: INACTIVE  ❌
```

**→ KEINE FIREWALL AKTIV! Alle Ports sind öffentlich erreichbar!**

---

## 📊 Offene Ports (22 gefunden):

### ✅ NOTWENDIG (öffentlich):
```
22    - SSH (notwendig für Admin-Zugriff)
80    - HTTP (nginx)
443   - HTTPS (nginx)
```

### ⚠️ GEFÄHRLICH (sollten NUR localhost sein):
```
3000  - Docker Proxy (öffentlich!)  ⚠️
5432  - PostgreSQL (öffentlich!)    ⚠️ KRITISCH!
6333  - Qdrant Vector DB (öffentlich!) ⚠️
8000  - Backend uvicorn (öffentlich!)  ⚠️
11434 - Ollama LLM (öffentlich!)     ⚠️
```

### ✅ OK (nur localhost):
```
127.0.0.1:53      - systemd-resolve (DNS)
127.0.0.1:36971   - containerd
127.0.0.1:37227   - node
127.0.0.1:40055   - language_server
127.0.0.1:42395   - language_server
127.0.0.1:45199   - node
```

---

## 🚨 SICHERHEITSRISIKEN:

### 1. PostgreSQL (Port 5432) öffentlich!
```
❌ Jeder kann versuchen auf deine DB zuzugreifen!
❌ Password-Brute-Force möglich!
❌ Datendiebstahl-Risiko!
```

### 2. Backend (Port 8000) öffentlich!
```
❌ Direct Backend-Access (nginx sollte einziger Zugang sein)
❌ API kann direkt attackiert werden
```

### 3. Ollama (Port 11434) öffentlich!
```
❌ Kostenloser LLM-Zugang für jeden!
❌ Kann missbraucht werden (DoS, Abuse)
```

### 4. Qdrant (Port 6333) öffentlich!
```
❌ Vector DB öffentlich zugänglich
❌ Embedding-Daten können gestohlen werden
```

---

## 🔧 SOFORT-MASSNAHMEN:

### 1. Firewall aktivieren:
```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable
```

### 2. PostgreSQL auf localhost binden:
```bash
# docker-compose.yml oder postgres config:
ports:
  - "127.0.0.1:5432:5432"  # NUR localhost!
```

### 3. Ollama auf localhost binden:
```bash
# /etc/systemd/system/ollama.service
Environment="OLLAMA_HOST=127.0.0.1:11434"
```

### 4. Backend über nginx laufen lassen:
```bash
# Backend NUR auf localhost:
--host 127.0.0.1 --port 8000
```

### 5. Qdrant auf localhost:
```bash
# docker-compose.yml:
ports:
  - "127.0.0.1:6333:6333"
```

---

## 📋 EMPFOHLENE FIREWALL-REGELN:

```bash
# Basis-Regeln
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Erlaubte öffentliche Ports
sudo ufw allow 22/tcp comment 'SSH'
sudo ufw allow 80/tcp comment 'HTTP'
sudo ufw allow 443/tcp comment 'HTTPS'

# Alles andere: DENY
sudo ufw enable

# Status prüfen
sudo ufw status numbered
```

---

## ⚠️ WICHTIG:

**BEVOR du ufw enable machst:**
- ✅ SSH-Port 22 ist erlaubt (sonst sperrst du dich aus!)
- ✅ Du hast SSH-Zugang zum Server
- ✅ Backup-Zugang vorhanden

---

## 🎯 PRIORITÄT:

1. **SOFORT:** Firewall aktivieren
2. **HEUTE:** Dienste auf localhost binden
3. **HEUTE:** Docker-Container neu konfigurieren

**Aktuell ist dein Server WEIT OFFEN!** ⚠️
