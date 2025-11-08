# 🔍 DEBUG: Sidebar zeigt keine Conversations

## Im Browser (F12 Console) ausführen:

```javascript
// 1. Check ob Conversations im localStorage sind
const convs = JSON.parse(localStorage.getItem('kiana.convs.v1') || '[]')
console.log('Conversations im localStorage:', convs.length)
console.log('Details:', convs)

// 2. Check ob convs-Variable im Code gesetzt ist
console.log('window.convs:', window.convs)

// 3. Check ob Sidebar-Element existiert
const sidebar = document.querySelector('.chat-list') || document.getElementById('chatList')
console.log('Sidebar Element:', sidebar)
console.log('Sidebar innerHTML:', sidebar ? sidebar.innerHTML : 'nicht gefunden')

// 4. Manuell rendern
if (typeof renderConversationList === 'function') {
  console.log('Versuche manuell zu rendern...')
  renderConversationList()
} else {
  console.log('renderConversationList nicht gefunden!')
}
```

**Kopiere die Ausgabe und schick sie mir!**

---

## Alternative: Screenshot

Mach einen Screenshot von der Chat-Seite und zeig mir wie sie aussieht.
