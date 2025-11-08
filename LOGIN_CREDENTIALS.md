# 🔐 Login-Credentials für ki-ana.at

**Datum:** 23. Oktober 2025, 11:20 Uhr

---

## 🌐 FÜR KI-ANA.AT (Docker Backend)

### **Deine Haupt-Accounts:**

**1. Gerald (Papa/Admin):**
```
Username: gerald
Passwort: Jawohund2011!
Rollen: papa, admin
```

**2. Test User:**
```
Username: test
Passwort: Test12345!
Rollen: admin, papa
```

**3. Admin Demo:**
```
Username: admin
Passwort: admin123
Rollen: admin
```

---

## 💻 FÜR LOCALHOST:8000 (Netapi Backend)

**Andere User in PostgreSQL!**

Um User zu erstellen/ändern:
```bash
cd /home/kiana/ki_ana
source .venv/bin/activate
python scripts/reset_password.py
```

---

## 🔧 PROBLEM-LÖSUNG

**Wenn Login nicht funktioniert:**

1. **Welche Seite nutzt du?**
   - `https://ki-ana.at/static/login.html` → Nutze Gerald/Test Credentials
   - `http://localhost:8000/...` → Nutze lokale DB-User

2. **Passwort vergessen?**
   - Docker Backend: Passwörter sind hart-codiert (siehe oben)
   - Netapi Backend: `python scripts/reset_password.py`

3. **Credentials testen:**
```bash
# Für ki-ana.at
curl -X POST https://ki-ana.at/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"gerald","password":"Jawohund2011!"}'

# Für localhost
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"dein_user","password":"dein_pw"}'
```

---

## ⚠️ WICHTIG

**ki-ana.at nutzt DOCKER Backend mit hart-codierten Usern!**

Wenn du neue User brauchst oder Passwörter ändern willst:
1. Datei bearbeiten: `/home/kiana/ki_ana/backend/auth/routes.py`
2. Container neu bauen: `docker compose build backend`
3. Container neu starten: `docker compose up -d backend`

---

**Probiere jetzt:**
- Username: `gerald`
- Passwort: `Jawohund2011!`
- Auf: https://ki-ana.at/static/login.html
