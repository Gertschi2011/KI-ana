# 🔍 DEBUG: Chat Storage Keys

## Im PC-Browser (F12 Console) ausführen:

### 1. Prüfe ALLE localStorage Keys:
```javascript
console.log('All localStorage keys:', Object.keys(localStorage))
```

### 2. Prüfe spezifische Keys:
```javascript
// Mögliche Keys basierend auf Code:
console.log('kiana_convs:', localStorage.getItem('kiana_convs'))
console.log('ki_ana_convs:', localStorage.getItem('ki_ana_convs'))
console.log('conversations:', localStorage.getItem('conversations'))

// Prüfe alle Keys die mit "conv" beginnen
Object.keys(localStorage).forEach(k => {
  if (k.includes('conv')) {
    console.log(k, ':', localStorage.getItem(k))
  }
})
```

### 3. Prüfe sessionStorage:
```javascript
console.log('sessionStorage keys:', Object.keys(sessionStorage))
```

### 4. Teste API direkt:
```javascript
// Liste alle Conversations vom Server
fetch('/api/chat/conversations', {
  credentials: 'include'
}).then(r => r.json()).then(d => console.log('Server convs:', d))
```

---

## Kopiere die Ausgabe und sag mir was du siehst!
