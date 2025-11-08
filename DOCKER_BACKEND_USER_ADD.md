# 🔐 Docker Backend - User hinzufügen

**Datum:** 23. Oktober 2025, 11:45 Uhr

---

## 🎯 DAS PROBLEM

**ki-ana.at nutzt das Docker Backend mit nur 3 hart-codierten Usern:**

```python
_USERS = {
    "admin@example.com": {...},      # admin / admin123
    "gerald@ki-ana.at": {...},       # gerald / Jawohund2011!
    "test@ki-ana.at": {...},         # test / Test12345!
}
```

**Dein User ist NICHT dabei!**

---

## ✅ DIE LÖSUNG

### **Option 1: Deinen User hinzufügen**

**Datei:** `/home/kiana/ki_ana/backend/auth/routes.py`

**Füge hinzu:**
```python
# Dein User
_USERS["dein-email@domain.com"] = {
    "password": hash_password("DeinPasswort123!"),
    "roles": ["papa", "admin"],
}
```

**Dann:**
```bash
cd /home/kiana/ki_ana
docker compose build backend
docker compose up -d backend
```

---

### **Option 2: Registrierung aktivieren**

Die `/api/auth/register` Route existiert bereits!

**Problem:** Frontend hat keinen Register-Button der funktioniert.

**Lösung:** Register-Seite fixen oder direkt API nutzen:

```bash
curl -X POST https://ki-ana.at/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "dein-email@domain.com",
    "password": "DeinPasswort123!"
  }'
```

---

## 🤔 WAS MÖCHTEST DU?

**Bitte sag mir:**

1. **Deine E-Mail:** (z.B. kiana@ki-ana.at)
2. **Dein Passwort:** (wird gehasht gespeichert)
3. **Deine Rollen:** papa, admin, user?

**Dann füge ich dich hinzu und baue den Container neu!**

---

## 📝 WICHTIG

**Das Docker Backend ist NICHT mit PostgreSQL verbunden!**

Es nutzt nur die hart-codierten User in `backend/auth/routes.py`.

Wenn du einen User hinzufügst, muss der Container neu gebaut werden.

---

**Sag mir deine Credentials und ich füge dich hinzu!** 💪
