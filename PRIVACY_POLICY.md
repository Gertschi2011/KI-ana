# 🔒 KI_ana OS - Privacy Policy

**Version:** 3.0.0  
**Effective Date:** 23. Oktober 2025  
**Last Updated:** 23. Oktober 2025

---

## 🎯 Our Privacy Commitment

**KI_ana OS is built with privacy as the foundation.**

- ✅ **100% Local:** All your data stays on your devices
- ✅ **No Cloud:** No data sent to external servers
- ✅ **No Tracking:** No analytics, no cookies, no tracking
- ✅ **Open Source:** Transparent code you can audit
- ✅ **Your Control:** You own and control all your data

---

## 📊 What Data We Collect

### **Core Application:**

**We collect ZERO data by default.**

- ❌ No personal information
- ❌ No IP addresses
- ❌ No device identifiers
- ❌ No usage analytics
- ❌ No crash reports
- ❌ No telemetry

**Everything runs 100% locally on your devices.**

---

### **Optional Telemetry (Opt-in Only):**

If you **explicitly opt-in** to telemetry, we collect:

**Anonymous Metrics Only:**
- Average latency (ms)
- Error rate (%)
- Peer count
- Block sync time (ms)

**Stored Locally:**
- All metrics stored on your device
- Never sent to external servers
- You can delete anytime

**What We DON'T Collect:**
- ❌ Personal information
- ❌ IP addresses
- ❌ Device identifiers
- ❌ Message content
- ❌ User data
- ❌ Location data
- ❌ Browsing history

---

## 🔐 How We Use Your Data

### **Local Processing:**

All data processing happens **locally on your devices:**

- **Embeddings:** Generated locally (sentence-transformers)
- **Vector Search:** Stored locally (Qdrant/ChromaDB)
- **Voice:** Processed locally (Whisper/Piper)
- **Messages:** Encrypted end-to-end (NaCl)
- **Blockchain:** Synced P2P (no central server)

### **P2P Communication:**

When you connect to other devices:

- **Direct Connection:** P2P via WebRTC
- **Encrypted:** End-to-end encryption (E2E)
- **No Intermediary:** No central server
- **Your Network:** Only devices you trust

### **Optional TURN Server:**

If you use a TURN server for NAT traversal:

- **Relay Only:** Only relays encrypted packets
- **No Decryption:** Cannot read your data
- **No Logging:** No data retention
- **Your Choice:** You can self-host

---

## 🛡️ Data Security

### **Encryption:**

- **At Rest:** AES-256 encryption
- **In Transit:** TLS 1.3 + E2E encryption
- **Keys:** Stored locally, 600 permissions
- **Rotation:** Automatic every 30 days

### **Access Control:**

- **Your Devices Only:** No external access
- **Trust-Based:** You control who connects
- **Revocation:** Instant key revocation
- **Emergency Override:** Kill-switch available

---

## 👤 Your Rights

### **You Have Full Control:**

1. **Access:** View all your data anytime
2. **Export:** Export all data (JSON, CSV)
3. **Delete:** Delete all data permanently
4. **Opt-Out:** Disable telemetry anytime
5. **Portability:** Move data to other devices

### **How to Exercise Your Rights:**

```bash
# View all data
ls -la ~/ki_ana/data/

# Export data
./scripts/export-data.sh

# Delete all data
./scripts/delete-all-data.sh

# Opt-out of telemetry
python -c "from system.telemetry import get_telemetry_service; get_telemetry_service().opt_out()"
```

---

## 🌐 Third-Party Services

### **We Use NO Third-Party Services:**

- ❌ No Google Analytics
- ❌ No Facebook Pixel
- ❌ No Advertising Networks
- ❌ No Cloud Providers
- ❌ No CDNs
- ❌ No External APIs

### **Optional Integrations:**

If you **choose** to integrate:

- **Ollama:** Self-hosted LLM (your server)
- **TURN Server:** Self-hosted relay (your server)
- **Custom APIs:** Your choice, your control

**We never force external dependencies.**

---

## 🔄 Data Retention

### **Local Storage:**

- **Your Control:** You decide how long to keep data
- **Auto-Cleanup:** Optional (configurable)
- **Backups:** Local only (your choice)

### **Telemetry (if opted-in):**

- **Local Only:** Stored on your device
- **Retention:** 90 days (configurable)
- **Deletion:** Automatic or manual

---

## 🌍 International Data Transfers

**There are NO international data transfers.**

- ✅ All data stays on your devices
- ✅ No cloud storage
- ✅ No cross-border transfers
- ✅ GDPR compliant by design
- ✅ CCPA compliant by design

---

## 👶 Children's Privacy

**KI_ana OS does not collect data from anyone, including children.**

- No age verification required
- No data collection
- Safe for all ages

---

## 📧 Contact Us

**Questions about privacy?**

- **Email:** privacy@kiana.ai
- **GitHub:** https://github.com/your-org/ki_ana/issues
- **Discord:** https://discord.gg/kiana

---

## 🔄 Changes to This Policy

**We will notify you of any changes:**

- **Version History:** See CHANGELOG.md
- **Notification:** In-app notification
- **Effective Date:** 30 days after announcement

**Last Updated:** 23. Oktober 2025

---

## ✅ Privacy Checklist

- [x] ✅ No data collection by default
- [x] ✅ 100% local processing
- [x] ✅ End-to-end encryption
- [x] ✅ No third-party services
- [x] ✅ Open source & auditable
- [x] ✅ User control & ownership
- [x] ✅ GDPR compliant
- [x] ✅ CCPA compliant
- [x] ✅ Transparent & honest

---

## 🏆 Privacy-First Principles

1. **Privacy by Design:** Built-in, not bolted-on
2. **Privacy by Default:** No opt-out needed
3. **Data Minimization:** Collect nothing by default
4. **User Control:** You own your data
5. **Transparency:** Open source & auditable
6. **Security:** Encrypted & protected
7. **No Tracking:** Ever.

---

**KI_ana OS: Privacy-First AI for Everyone** 🔒

---

**Version:** 3.0.0  
**Effective:** 23. Oktober 2025  
**Contact:** privacy@kiana.ai
