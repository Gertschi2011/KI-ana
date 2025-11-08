# 🔍 DEBUG loadMessages

## Im Browser Console (F12):

```javascript
// Test loadMessages direkt
const activeConv = localStorage.getItem('kiana.activeConv.v1')
console.log('activeConv:', activeConv)

// Test loadMessages
const CONV_PREFIX = 'kiana.conv.'
const raw = localStorage.getItem(CONV_PREFIX + activeConv)
console.log('raw storage:', raw)

// Was gibt loadMessages zurück?
const parsed = raw ? JSON.parse(raw) : []
console.log('parsed:', parsed)
console.log('isArray:', Array.isArray(parsed))
```

Schick mir die Ausgabe!
