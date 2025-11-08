# 🔒 FIREWALL MANUELL AKTIVIEREN

Kopiere diese Befehle **EINZELN** ins Terminal:

```bash
# 1. Defaults setzen
sudo ufw default deny incoming
sudo ufw default allow outgoing

# 2. Ports erlauben
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# 3. Firewall aktivieren
sudo ufw --force enable

# 4. Status prüfen
sudo ufw status numbered
```

**Führe jeden Befehl einzeln aus und gib dein Passwort ein!**

---

## ODER: Als Root

```bash
sudo -i
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable
ufw status numbered
exit
```
