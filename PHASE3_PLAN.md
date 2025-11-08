# 🚀 Phase 3: P2P-Netzwerk & Federated Learning

**Zeitraum:** Q1 2026 - 3-6 Monate  
**Start:** November 2025  
**Status:** 📋 Planung

---

## 🎯 Hauptziele

**Phase 3 Vision:** Subminds kommunizieren direkt miteinander ohne zentrale Instanz

### **Kernfeatures:**
1. 🌐 **Device Discovery** - Automatische Erkennung im LAN
2. 🔗 **P2P-Kommunikation** - Direkte Verbindungen zwischen Devices
3. 🧠 **Block-Sync** - Dezentraler Wissensaustausch
4. 🧩 **Federated Learning** - Gemeinsames Lernen ohne Datenaustausch

---

## 📅 Wochenplan (12-16 Wochen)

### **Woche 1-2: Device Discovery (mDNS)**
**Ziel:** Automatische Erkennung von Subminds im Netzwerk

**Tasks:**
- [ ] mDNS/Bonjour Service implementieren
- [ ] Device Announcement (Broadcast)
- [ ] Device Discovery (Scan)
- [ ] Service Registration
- [ ] Heartbeat-Mechanismus

**Technologie:**
```python
# mDNS mit Zeroconf
from zeroconf import ServiceInfo, Zeroconf

# Service registrieren
info = ServiceInfo(
    "_kiana._tcp.local.",
    "submind-001._kiana._tcp.local.",
    addresses=[socket.inet_aton("192.168.1.100")],
    port=8000,
    properties={
        'device_id': 'uuid',
        'role': 'submind',
        'capabilities': 'sensors,compute'
    }
)
```

**Erfolgskriterien:**
- ✅ Devices finden sich automatisch im LAN
- ✅ Service-Info wird ausgetauscht
- ✅ Offline-Devices werden erkannt
- ✅ Latenz < 5s für Discovery

---

### **Woche 3-4: WebRTC P2P-Verbindungen**
**Ziel:** Direkte Peer-to-Peer Kommunikation

**Tasks:**
- [ ] WebRTC Signaling Server (optional)
- [ ] STUN/TURN Server Setup
- [ ] P2P Connection Establishment
- [ ] Data Channels
- [ ] NAT Traversal

**Technologie:**
```python
# aiortc für WebRTC
from aiortc import RTCPeerConnection, RTCDataChannel

# P2P Connection
pc = RTCPeerConnection()
channel = pc.createDataChannel("kiana-sync")

# Signaling via mDNS oder HTTP
```

**Erfolgskriterien:**
- ✅ Direkte Verbindung zwischen 2 Devices
- ✅ NAT Traversal funktioniert
- ✅ Data Channel stabil
- ✅ Latenz < 100ms im LAN

---

### **Woche 5-6: Block-Sync Mechanismus**
**Ziel:** Wissensblöcke zwischen Subminds synchronisieren

**Tasks:**
- [ ] Block-Format definieren
- [ ] Sync-Protokoll implementieren
- [ ] Conflict Resolution
- [ ] Merkle Tree für Effizienz
- [ ] Delta-Sync

**Technologie:**
```python
# Block-Sync
class BlockSync:
    def sync_blocks(self, peer_id: str):
        # 1. Get peer's block hashes
        peer_hashes = self.get_peer_hashes(peer_id)
        
        # 2. Compare with local
        missing = self.find_missing_blocks(peer_hashes)
        
        # 3. Request missing blocks
        blocks = self.request_blocks(peer_id, missing)
        
        # 4. Validate & store
        self.validate_and_store(blocks)
```

**Erfolgskriterien:**
- ✅ Blocks werden zwischen Peers ausgetauscht
- ✅ Keine Duplikate
- ✅ Konflikte werden aufgelöst
- ✅ Effizienter Delta-Sync

---

### **Woche 7-8: Dezentrale Blockchain**
**Ziel:** Blocks werden über P2P-Netzwerk verteilt

**Tasks:**
- [ ] Block Validation erweitern
- [ ] Distributed Consensus (optional)
- [ ] Block Propagation
- [ ] Chain Verification
- [ ] Byzantine Fault Tolerance (optional)

**Konzept:**
```
Block erstellt auf Submind A
    ↓
Wird signiert (Ed25519) ✅
    ↓
Wird an Peers propagiert (P2P)
    ↓
Jeder Peer validiert (chain_validator.json)
    ↓
Block wird in lokale Chain integriert
```

**Erfolgskriterien:**
- ✅ Blocks propagieren automatisch
- ✅ Jeder Submind hat vollständige Chain
- ✅ Manipulation wird erkannt
- ✅ Performance akzeptabel

---

### **Woche 9-10: Federated Learning Basis**
**Ziel:** Gemeinsames Lernen ohne Datenaustausch

**Tasks:**
- [ ] Model Update Aggregation
- [ ] Differential Privacy
- [ ] Secure Aggregation
- [ ] Model Versioning
- [ ] Performance Tracking

**Federated Learning Ansatz:**
```python
# Jeder Submind lernt lokal
class FederatedLearner:
    def train_local(self, data):
        # 1. Lokales Training
        model_update = self.model.train(data)
        
        # 2. Nur Updates teilen (nicht Daten!)
        return model_update
    
    def aggregate_updates(self, updates):
        # 3. Updates von allen Peers sammeln
        # 4. Durchschnitt bilden
        aggregated = average(updates)
        
        # 5. Lokales Model aktualisieren
        self.model.apply_update(aggregated)
```

**Privacy-Garantie:**
- ✅ Rohdaten bleiben auf Device
- ✅ Nur anonymisierte Updates werden geteilt
- ✅ Differential Privacy (optional)
- ✅ Jeder Submind kann Sync ablehnen

**Erfolgskriterien:**
- ✅ Model-Updates werden ausgetauscht
- ✅ Keine Rohdaten verlassen Device
- ✅ Aggregation funktioniert
- ✅ Alle profitieren vom gemeinsamen Wissen

---

### **Woche 11-12: P2P-Messaging**
**Ziel:** Direkte Kommunikation zwischen Subminds

**Tasks:**
- [ ] Message Queue System
- [ ] End-to-End Encryption
- [ ] Message Routing
- [ ] Offline Message Storage
- [ ] Delivery Confirmation

**Technologie:**
```python
# E2E verschlüsselte Messages
from nacl.public import PrivateKey, Box

# Nachricht senden
def send_message(peer_id: str, message: str):
    # 1. Peer's Public Key holen
    peer_key = get_peer_public_key(peer_id)
    
    # 2. Verschlüsseln
    box = Box(my_private_key, peer_key)
    encrypted = box.encrypt(message.encode())
    
    # 3. Über P2P senden
    send_to_peer(peer_id, encrypted)
```

**Erfolgskriterien:**
- ✅ Messages werden zugestellt
- ✅ E2E verschlüsselt
- ✅ Offline-Messages werden gespeichert
- ✅ Delivery Confirmation

---

### **Woche 13-14: Network Resilience**
**Ziel:** Robustes P2P-Netzwerk

**Tasks:**
- [ ] Peer Failure Detection
- [ ] Automatic Reconnection
- [ ] Network Partitioning Handling
- [ ] Gossip Protocol
- [ ] Load Balancing

**Erfolgskriterien:**
- ✅ Netzwerk überlebt Peer-Ausfälle
- ✅ Automatische Wiederverbindung
- ✅ Partitionen werden geheilt
- ✅ Keine Single Point of Failure

---

### **Woche 15-16: Integration & Testing**
**Ziel:** Alles zusammenführen & testen

**Tasks:**
- [ ] End-to-End Tests (3+ Devices)
- [ ] Performance-Optimierung
- [ ] Security Audit
- [ ] Dokumentation
- [ ] Deployment-Guide

**Test-Szenarien:**
```
Szenario 1: 3 Devices im LAN
├── Device Discovery
├── P2P Connections
├── Block-Sync
└── Federated Learning

Szenario 2: NAT Traversal
├── Devices hinter Router
├── STUN/TURN
└── Connection Establishment

Szenario 3: Network Partition
├── Devices getrennt
├── Offline-Betrieb
└── Merge nach Reconnect
```

---

## 🛠️ Technologie-Stack (Phase 3)

### **Neu hinzugefügt:**
```
Networking:
├── zeroconf (mDNS)
├── aiortc (WebRTC)
├── STUN/TURN Server
└── Gossip Protocol

Security:
├── NaCl (Encryption)
├── Ed25519 (Signing)
└── TLS (Transport)

Sync:
├── Merkle Trees
├── Delta-Sync
└── CRDT (optional)
```

### **Weiterhin verwendet:**
```
Core (Phase 2):
├── sentence-transformers
├── ChromaDB
├── Whisper + Piper
├── SQLite
└── Submind-System
```

---

## 📊 Metriken & KPIs

### **Performance-Ziele:**
- **Device Discovery:** < 5s
- **P2P Connection:** < 2s
- **Block-Sync:** < 10s für 100 Blocks
- **Message Delivery:** < 1s im LAN
- **Federated Learning:** 1 Round < 60s

### **Qualitäts-Ziele:**
- **Uptime:** > 99%
- **Data Loss:** 0%
- **Security:** E2E encrypted
- **Privacy:** No raw data shared

### **Skalierbarkeit:**
- **Peers:** 10-100 Devices
- **Blocks:** 10.000+ pro Device
- **Messages:** 1.000+ pro Tag
- **Network:** LAN + Internet

---

## 🚧 Risiken & Mitigationen

### **Risiko 1: NAT Traversal**
**Problem:** Devices hinter Router nicht erreichbar  
**Mitigation:**
- STUN/TURN Server
- UPnP/NAT-PMP
- Relay-Fallback

### **Risiko 2: Network Partitioning**
**Problem:** Netzwerk wird getrennt  
**Mitigation:**
- Offline-First Design
- Conflict Resolution
- Eventual Consistency

### **Risiko 3: Sybil Attacks**
**Problem:** Böswillige Peers  
**Mitigation:**
- Trust Levels
- Reputation System
- Rate Limiting

### **Risiko 4: Komplexität**
**Problem:** P2P ist komplex  
**Mitigation:**
- Schrittweise Implementation
- Gute Tests
- Fallback auf zentral

---

## 📝 Deliverables

### **Code:**
- [ ] `system/p2p_discovery.py`
- [ ] `system/p2p_connection.py`
- [ ] `system/block_sync.py`
- [ ] `system/federated_learning.py`
- [ ] `system/p2p_messaging.py`

### **Dokumentation:**
- [ ] `docs/P2P_SETUP.md`
- [ ] `docs/FEDERATED_LEARNING.md`
- [ ] `docs/SECURITY.md`
- [ ] `docs/TROUBLESHOOTING.md`

### **Tests:**
- [ ] `tests/test_p2p_discovery.py`
- [ ] `tests/test_block_sync.py`
- [ ] `tests/test_federated_learning.py`
- [ ] `tests/test_network_resilience.py`

---

## 🎯 Definition of Done

Phase 3 ist abgeschlossen wenn:

1. ✅ **Device Discovery:**
   - Automatische Erkennung im LAN
   - Service-Info Austausch
   - Heartbeat funktioniert

2. ✅ **P2P-Kommunikation:**
   - Direkte Verbindungen
   - NAT Traversal
   - Data Channels stabil

3. ✅ **Block-Sync:**
   - Blocks werden ausgetauscht
   - Konflikte aufgelöst
   - Delta-Sync effizient

4. ✅ **Federated Learning:**
   - Model-Updates aggregiert
   - Privacy gewahrt
   - Alle profitieren

5. ✅ **Qualität:**
   - Alle Tests passing
   - Performance-Ziele erreicht
   - Dokumentation vollständig

6. ✅ **Production:**
   - Deployment-Guide
   - Security Audit
   - Multi-Device getestet

---

## 🔄 Phase 2 → 3 Übergang

### **Was bereits vorhanden ist:**
```
✅ Submind-System (Device Identity)
✅ Submind Registry
✅ Rollen & Permissions
✅ Trust Levels
✅ Sync-Client (HTTP-basiert)
✅ Block-Struktur
✅ Signierung (Ed25519)
```

### **Was neu kommt:**
```
🆕 mDNS Discovery
🆕 WebRTC P2P
🆕 Dezentraler Sync
🆕 Federated Learning
🆕 E2E Messaging
```

### **Migration-Path:**
```
Phase 2 (Zentral):
Mother-KI ← HTTP → Submind

Phase 3 (P2P):
Submind ← WebRTC → Submind
   ↓
Mother-KI (optional)
```

---

## 💡 Use Cases (Phase 3)

### **Use Case 1: Familie**
```
Wohnzimmer (Raspberry Pi):
├── Koordiniert Smart Home
├── Sammelt Sensor-Daten
└── Synct mit allen Devices

Smartphone (Mama):
├── Voice Interface
├── Feedback geben
└── Lernt von anderen

Tablet (Kind):
├── Lernt von Eltern-Devices
├── Eingeschränkte Permissions
└── Offline-fähig
```

### **Use Case 2: Team**
```
Server (Zentral):
├── Optional für Backup
└── Koordiniert große Syncs

Laptops (Entwickler):
├── Lernen gemeinsam
├── Teilen Code-Patterns
└── P2P im Office-LAN

Mobile (Field):
├── Sammelt Daten offline
├── Synct bei Verbindung
└── Profitiert von Team-Wissen
```

### **Use Case 3: IoT-Netzwerk**
```
Hub (Raspberry Pi):
├── Koordiniert Sensoren
└── Aggregiert Daten

Sensoren (ESP32):
├── Sammeln Umwelt-Daten
├── Senden via P2P
└── Minimal Overhead

Smartphone (User):
├── Visualisierung
├── Steuerung
└── Feedback
```

---

## 🎓 Learnings aus Phase 2

### **Was wir mitnehmen:**
1. ✅ Singleton Pattern funktioniert gut
2. ✅ JSON für Config ist einfach
3. ✅ Batch-Processing ist wichtig
4. ✅ Tests parallel entwickeln
5. ✅ Dokumentation ist Gold wert

### **Was wir vermeiden:**
1. ❌ Zu komplexe Architekturen
2. ❌ Zu viele Dependencies
3. ❌ Fehlende Tests
4. ❌ Unklare Dokumentation

---

## 🚀 Sofort starten?

### **Quick Start (Woche 1):**
```bash
# 1. mDNS installieren
pip install zeroconf

# 2. Discovery Service erstellen
python system/p2p_discovery.py

# 3. Testen
python tests/test_p2p_discovery.py
```

---

**Erstellt:** 23. Oktober 2025, 08:00 Uhr  
**Status:** 📋 Bereit zum Start  
**Nächstes Review:** Nach Woche 2 (Device Discovery)
