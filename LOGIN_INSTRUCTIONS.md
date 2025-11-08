# 🔐 LOGIN ANLEITUNG

## ❗ WICHTIG - BITTE BEFOLGEN:

### 1. Browser-Cache leeren!

**Das Problem:** Dein Browser hat vermutlich alte Login-Daten gecached!

**Lösung:**
```
1. Chrome/Edge: Strg+Shift+Delete
2. Wähle "Cached images and files"
3. Klicke "Clear data"

ODER einfach:
- Private/Inkognito-Fenster öffnen
- Dort https://ki-ana.at/login aufrufen
```

---

### 2. Exakte Login-Daten:

```
Username: Gerald
(GROSS geschrieben! Nicht "gerald" klein)

Password: Jawohund2011!
(Exakt so, mit Großbuchstaben und Ausrufezeichen)
```

**ODER mit Email:**
```
Username: gerald.stiefsohn@gmx.at
Password: Jawohund2011!
```

---

### 3. Teste im Inkognito-Fenster:

```
1. Öffne Inkognito/Private-Fenster
2. Gehe zu: https://ki-ana.at/login
3. Eingabe:
   - Username: Gerald
   - Password: Jawohund2011!
4. Login klicken
```

---

## 📊 Backend-Status:

✅ Backend läuft korrekt  
✅ User "Gerald" ist in DB  
✅ Passwort ist gesetzt  
✅ Test-Login von Server funktioniert (200 OK)

**Die 401-Fehler kommen nur vom Browser - vermutlich wegen Cache oder falscher Eingabe!**

---

## 🧪 Verifikation:

Das Backend-Log zeigt:
```
INFO: 152.53.128.59:0 - "POST /api/auth/login HTTP/1.1" 200 OK
```

→ Login funktioniert vom Server aus!

Aber:
```
INFO: 77.119.239.224:0 - "POST /api/auth/login HTTP/1.1" 401 Unauthorized
```

→ Von deiner IP (77.119.239.224) kommt 401 - falsches Passwort oder Username?

---

## 💡 Checklist:

- [ ] Browser-Cache geleert?
- [ ] Inkognito-Fenster verwendet?
- [ ] Username EXAKT "Gerald" (groß G)?
- [ ] Password EXAKT "Jawohund2011!" ?
- [ ] Keine Leerzeichen vor/nach?

**Wenn das alles stimmt, sollte es funktionieren!** ✅
