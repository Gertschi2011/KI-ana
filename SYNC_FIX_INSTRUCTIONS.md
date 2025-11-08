# 🔄 CHAT SYNC FIX - Am 2. PC

## Problem:
- Login funktioniert ✅
- Aber Chats werden nicht angezeigt ❌

---

## Im Browser (F12 Console) ausführen:

```javascript
// 1. Check ob eingeloggt
fetch('/api/me', {credentials: 'include'})
  .then(r => r.json())
  .then(d => console.log('Auth:', d))

// 2. Lade Conversations manuell
fetch('/api/chat/conversations', {credentials: 'include'})
  .then(r => r.json())
  .then(d => {
    console.log('Server conversations:', d)
    
    // 3. Füge sie zur lokalen Liste hinzu
    if (d.ok && d.items && window.convs) {
      d.items.forEach(c => {
        const lid = 'srv-' + c.id
        if (!window.convs.find(x => x.id === lid)) {
          window.convs.push({
            id: lid,
            title: c.title,
            createdAt: c.created_at * 1000,
            updatedAt: c.updated_at * 1000
          })
        }
      })
      
      // Speichern und neu rendern
      if (typeof saveConvs === 'function') saveConvs()
      if (typeof renderConversationList === 'function') renderConversationList()
      
      console.log('✅ Conversations synced!')
    }
  })
```

---

## ODER: Seite komplett neu laden

```javascript
location.reload()
```

Dann sollte `bootstrapAuthAndSync()` automatisch laufen.
