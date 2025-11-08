# ❓ KI_ana OS - Häufig gestellte Fragen (FAQ)

**Version:** 3.0  
**Letzte Aktualisierung:** 23. Oktober 2025

---

## 🌟 Allgemein

### Was ist KI_ana OS?
KI_ana OS ist ein dezentrales, privacy-first KI-Betriebssystem mit Persönlichkeit. Es läuft komplett lokal auf deinen Geräten, synchronisiert sich P2P über WebRTC und bietet Federated Learning ohne zentrale Server.

### Warum KI_ana statt ChatGPT/Claude?
- ✅ **100% Privacy:** Alle Daten bleiben lokal
- ✅ **Offline-fähig:** Funktioniert ohne Internet
- ✅ **Kostenlos:** Keine monatlichen Gebühren
- ✅ **Multi-Device:** Synchronisiert über mehrere Geräte
- ✅ **Open Source:** Transparenter Code

### Ist KI_ana kostenlos?
Ja! KI_ana ist Open Source (MIT License) und komplett kostenlos. Keine versteckten Kosten, keine Abos.

---

## 💻 Installation

### Welche Systemanforderungen gibt es?
**Minimum:**
- CPU: 4 Cores
- RAM: 8GB
- Disk: 20GB
- OS: Linux, macOS, Windows (WSL2)
- Python: 3.10+

**Empfohlen:**
- CPU: 8+ Cores
- RAM: 16GB+
- Disk: 50GB+ SSD
- GPU: Optional (schnellere Embeddings)

### Wie installiere ich KI_ana?
**One-Line Install:**
```bash
curl -sSL https://get.kiana.ai | bash
```

**Oder manuell:** Siehe [QUICKSTART.md](QUICKSTART.md)

### Funktioniert KI_ana auf Raspberry Pi?
Ja! Ab Raspberry Pi 4 mit 4GB+ RAM. Performance ist langsamer, aber funktioniert.

---

## 🔐 Sicherheit & Privacy

### Werden meine Daten irgendwo hochgeladen?
**NEIN!** Alle Daten bleiben auf deinen Geräten. P2P-Sync erfolgt direkt zwischen deinen Geräten (E2E encrypted).

### Wie sicher ist die Verschlüsselung?
- **E2E Encryption:** NaCl (libsodium)
- **Key-Rotation:** Automatisch alle 30 Tage
- **Blockchain:** PoA Consensus mit Signature Verification

### Kann jemand meine Nachrichten mitlesen?
Nein. Alle Nachrichten sind End-to-End verschlüsselt. Nur du und deine Geräte können sie lesen.

### Was passiert wenn mein Gerät gehackt wird?
- **Key-Rotation:** Alte Keys werden ungültig
- **Emergency Override:** Sofortiges Abschalten möglich
- **Revocation-Liste:** Kompromittierte Keys sperren

---

## 🌐 Netzwerk & P2P

### Brauche ich Internet?
**Nein!** KI_ana funktioniert komplett offline. Internet ist nur für:
- Multi-Device Sync (WAN)
- Updates
- Optional: Public Node Registry

### Wie funktioniert Multi-Device?
- **LAN:** Automatische Discovery via mDNS
- **WAN:** WebRTC + TURN Server
- **Sync:** CRDT-basiert, konfliktfrei

### Was ist ein TURN Server?
Ein Relay-Server für NAT-Traversal. Ermöglicht P2P-Verbindungen über das Internet, auch hinter Firewalls.

### Muss ich einen TURN Server betreiben?
**Nein!** Im LAN funktioniert alles ohne TURN. Für WAN kannst du:
- Eigenen TURN Server (empfohlen)
- Public TURN Server (optional)
- Ohne TURN (nur LAN)

### Funktioniert KI_ana hinter CGNAT?
Ja, mit TURN Server. Ohne TURN nur im LAN.

---

## 🤖 KI & Features

### Welche KI-Modelle werden unterstützt?
- **Embeddings:** sentence-transformers (lokal)
- **LLM:** Ollama (llama2, mistral, etc.)
- **Voice:** Whisper (STT), Piper (TTS)

### Kann ich eigene Modelle verwenden?
Ja! Ollama unterstützt viele Modelle. Einfach installieren und in `.env` konfigurieren.

### Was ist ein "Submind"?
Ein Submind ist ein zusätzliches KI_ana-Gerät in deinem Netzwerk. Alle Subminds teilen Wissen und lernen gemeinsam (Federated Learning).

### Wie funktioniert Federated Learning?
- Jedes Gerät trainiert lokal
- Nur Model-Updates werden geteilt (keine Rohdaten!)
- FedAvg-Algorithmus für Aggregation

---

## 🎨 Desktop & UI

### Was ist der Avatar?
Ein animierter 2D-Avatar der KI_ana eine visuelle Persönlichkeit gibt. Reagiert auf Sprache und zeigt Emotionen.

### Funktioniert Voice-Control?
Ja! "Hey KI_ana" aktiviert Voice-Interface (Wake-Word Detection mit Porcupine).

### Kann ich das Design anpassen?
Ja! Dashboard ist HTML/CSS/JS - einfach anpassbar. Themes kommen in v3.1.

---

## 🔧 Troubleshooting

### Port 8000 schon belegt?
```bash
# Anderen Port verwenden
P2P_PORT=8001 uvicorn netapi.app:app --port 8001
```

### mDNS Discovery funktioniert nicht?
```bash
# Avahi installieren (Linux)
sudo apt install avahi-daemon

# Firewall öffnen
sudo ufw allow 5353/udp
```

### Import-Fehler?
```bash
# Dependencies neu installieren
pip install --force-reinstall -r requirements.txt
```

### Backup schlägt fehl?
```bash
# Permissions prüfen
chmod +x scripts/backup.sh

# Manuell ausführen
./scripts/backup.sh
```

---

## 📊 Performance

### Wie schnell ist KI_ana?
- **Embeddings:** ~92ms (lokal)
- **Vector Search:** ~100ms
- **Voice (STT):** 1-3s
- **P2P Connection:** <2s
- **Block-Sync:** <1s (Delta)

### Kann ich KI_ana beschleunigen?
- **GPU:** Für Embeddings (CUDA)
- **SSD:** Für Datenbank
- **RAM:** Mehr = schneller
- **CPU:** Mehr Cores = besser

---

## 🚀 Deployment

### Kann ich KI_ana in Production nutzen?
**Ja!** KI_ana ist production-ready:
- ✅ Monitoring (Prometheus)
- ✅ Auto-Backup
- ✅ Key-Rotation
- ✅ Health Checks
- ✅ Docker Support

### Wie skaliert KI_ana?
- **Horizontal:** Mehr Geräte = mehr Power
- **Vertical:** Bessere Hardware = schneller
- **Unbegrenzt:** Kein zentraler Bottleneck

---

## 🤝 Community

### Wo finde ich Hilfe?
- **Docs:** https://docs.kiana.ai
- **GitHub:** https://github.com/your-org/ki_ana
- **Discord:** https://discord.gg/kiana
- **Forum:** https://forum.kiana.ai

### Wie kann ich beitragen?
- **Code:** Pull Requests auf GitHub
- **Bugs:** Issues melden
- **Docs:** Dokumentation verbessern
- **Community:** Anderen helfen

### Gibt es einen Roadmap?
Ja! Siehe [PHASE5_ROADMAP.md](PHASE5_ROADMAP.md)

---

## 💰 Kosten

### Was kostet KI_ana im Betrieb?
**Nur Strom!**
- ~5-10W idle
- ~50-100W unter Last
- ~$5-15/Monat Strom (je nach Region)

**Vergleich zu Cloud:**
- ChatGPT Plus: $20/Monat
- Claude Pro: $20/Monat
- **KI_ana: $0/Monat** (nur Strom)

**Ersparnis:** $240-480/Jahr!

---

## 📱 Mobile

### Gibt es eine Mobile App?
Noch nicht. Geplant für v3.1:
- iOS App
- Android App
- PWA (schon verfügbar!)

### Funktioniert PWA auf Mobile?
Ja! Öffne Dashboard im Browser und "Add to Home Screen".

---

## 🔮 Zukunft

### Was kommt als Nächstes?
**v3.1 (Q1 2026):**
- Mobile Apps
- 3D-Avatar
- Advanced Voice
- Themes

**v3.2 (Q2 2026):**
- Multi-Language
- Plugin-System
- Marketplace

Siehe [ROADMAP.md](ROADMAP.md)

---

## ❓ Weitere Fragen?

**Nicht gefunden?**
- 📧 Email: support@kiana.ai
- 💬 Discord: https://discord.gg/kiana
- 🐛 GitHub Issues: https://github.com/your-org/ki_ana/issues

---

**Letzte Aktualisierung:** 23. Oktober 2025  
**Version:** 3.0
