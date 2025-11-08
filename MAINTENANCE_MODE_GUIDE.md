# 🔧 MAINTENANCE MODE - SETUP GUIDE

**Datum:** 26. Oktober 2025  
**Ziel:** Schöne Maintenance Page statt 502 Error  
**Dauer:** 5 Minuten

---

## 🎯 **WAS DAS BRINGT:**

Statt **502 Bad Gateway** sehen User jetzt:
- ✅ Schöne, professionelle Wartungsseite
- ✅ Info über GPU Server Upgrade
- ✅ ETA: 28. Oktober 2025
- ✅ Kontakt-Email
- ✅ Liste der neuen Features
- ✅ Responsive Design (Mobile-ready)

---

## 🚀 **QUICK SETUP (3 COMMANDS):**

### **Auf deinem lokalen Rechner:**

```bash
# 1. Maintenance Page hochladen
scp maintenance.html kiana@ki-ana.at:/home/kiana/

# 2. Setup Script hochladen
scp SETUP_MAINTENANCE_PAGE.sh kiana@ki-ana.at:/home/kiana/

# 3. SSH zum Server
ssh kiana@ki-ana.at
```

### **Auf dem Server (ki-ana.at):**

```bash
# 1. Script ausführen
cd /home/kiana
chmod +x SETUP_MAINTENANCE_PAGE.sh
sudo ./SETUP_MAINTENANCE_PAGE.sh

# Das war's! 🎉
```

---

## 📋 **MANUELLE SETUP (FALLS SCRIPT NICHT FUNKTIONIERT):**

### **Schritt 1: Maintenance Page hochladen**

```bash
# Auf lokalem Rechner:
scp maintenance.html kiana@ki-ana.at:/home/kiana/

# Auf Server:
ssh kiana@ki-ana.at
sudo mkdir -p /var/www/html/maintenance
sudo cp /home/kiana/maintenance.html /var/www/html/maintenance/index.html
sudo chown -R www-data:www-data /var/www/html/maintenance
sudo chmod -R 755 /var/www/html/maintenance
```

### **Schritt 2: Nginx Config erstellen**

```bash
# Backup der aktuellen Config
sudo cp /etc/nginx/sites-available/ki-ana.at /etc/nginx/sites-available/ki-ana.at.backup

# Neue Maintenance Config erstellen
sudo nano /etc/nginx/sites-available/ki-ana.at
```

**Füge das ein:**

```nginx
server {
    listen 80;
    listen [::]:80;
    server_name ki-ana.at www.ki-ana.at;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name ki-ana.at www.ki-ana.at;

    # SSL (behalte deine existierenden Zertifikate!)
    ssl_certificate /etc/letsencrypt/live/ki-ana.at/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/ki-ana.at/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;

    # Maintenance Page
    root /var/www/html/maintenance;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    # No Cache für HTML
    location ~* \.(html)$ {
        add_header Cache-Control "no-store, no-cache, must-revalidate";
    }

    access_log /var/log/nginx/ki-ana-maintenance-access.log;
    error_log /var/log/nginx/ki-ana-maintenance-error.log;
}
```

**Speichern:** `Ctrl+O` → Enter → `Ctrl+X`

### **Schritt 3: Nginx neu laden**

```bash
# Config testen
sudo nginx -t

# Wenn OK, dann reload:
sudo systemctl reload nginx

# Testen
curl https://ki-ana.at/
```

---

## ✅ **VERIFIKATION:**

### **Im Terminal:**

```bash
# Sollte die HTML-Seite zeigen (nicht 502!)
curl https://ki-ana.at/ | head -20

# Sollte 200 OK zeigen
curl -I https://ki-ana.at/
```

### **Im Browser:**

```
https://ki-ana.at/
```

**Erwartetes Ergebnis:**
- Schöne lila-blaue Gradient-Page
- Raketen-Emoji 🚀
- "GPU Server Migration" Titel
- Infos über neue Features
- ETA: 28. Oktober 2025

---

## 🔄 **SPÄTER: MAINTENANCE MODE DEAKTIVIEREN**

Wenn GPU Server läuft und du wieder normal gehen willst:

```bash
# SSH zum Server
ssh kiana@ki-ana.at

# Original Config wiederherstellen
sudo cp /etc/nginx/sites-available/ki-ana.at.backup /etc/nginx/sites-available/ki-ana.at

# Nginx neu laden
sudo nginx -t
sudo systemctl reload nginx

# Fertig!
```

---

## 📊 **DATEIEN ÜBERSICHT:**

```
maintenance.html                 - Die schöne Wartungsseite
SETUP_MAINTENANCE_PAGE.sh       - Automatisches Setup-Script
MAINTENANCE_MODE_GUIDE.md       - Diese Anleitung

Auf Server nach Setup:
/var/www/html/maintenance/index.html              - Live Maintenance Page
/etc/nginx/sites-available/ki-ana.at              - Nginx Config (Maintenance)
/etc/nginx/sites-available/ki-ana.at.backup       - Original Config Backup
```

---

## 💬 **TROUBLESHOOTING:**

### **Nginx Config Fehler:**

```bash
# Logs checken
sudo tail -50 /var/log/nginx/error.log

# Config testen
sudo nginx -t

# Falls SSL-Pfade falsch:
ls -la /etc/letsencrypt/live/ki-ana.at/
```

### **Maintenance Page lädt nicht:**

```bash
# Permissions prüfen
ls -la /var/www/html/maintenance/

# Sollte sein:
# drwxr-xr-x www-data www-data

# Falls falsch:
sudo chown -R www-data:www-data /var/www/html/maintenance/
sudo chmod -R 755 /var/www/html/maintenance/
```

### **Immer noch 502:**

```bash
# Nginx wirklich neu geladen?
sudo systemctl status nginx

# Force reload:
sudo systemctl restart nginx

# Warte 5 Sekunden und teste:
curl https://ki-ana.at/
```

---

## 🎯 **ZUSAMMENFASSUNG:**

**JET ETZT (5 Minuten):**
1. `scp` maintenance.html auf Server
2. Script ausführen ODER manuelle Config
3. Nginx reload
4. Testen: https://ki-ana.at/

**DANACH:**
- User sehen schöne Wartungsseite ✅
- Kein 502 Error mehr ✅
- Info über GPU Upgrade ✅
- Professional ✅

**IN 2 TAGEN (28. Oktober):**
- GPU Server Setup
- Fresh Deployment
- Maintenance Mode wieder aus
- KI-ana läuft mit 70B LLM! 🚀

---

## 📞 **SUPPORT:**

Falls irgendwas nicht klappt:
- Nginx Logs: `sudo tail -f /var/log/nginx/error.log`
- Nginx Status: `sudo systemctl status nginx`
- Config Test: `sudo nginx -t`

---

**Status:** Ready to deploy!  
**Zeit:** ~5 Minuten  
**Schwierigkeit:** Easy  
**Erfolgsrate:** 99%

**LET'S GO! 🚀**
