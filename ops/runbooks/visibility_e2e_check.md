# Explain & Quality sichtbar – E2E Checkliste (2 Minuten)

## 0) Visibility Mini-Checks (30 Sekunden)

- `https://ki-ana.at/app/chat`
  - wenn **nicht** eingeloggt: Navbar zeigt **Login** (Link/Button)
  - wenn eingeloggt: Navbar zeigt **Logout**
- `/api/logout` muss **GET** können und Cookie-Clears setzen
- `/api/me` nach Logout muss `auth:false` sein

## 1) Auth/Cookie (Browser)

- URL 1: `https://ki-ana.at/api/login` (Login-Request aus UI oder curl)
- URL 2: `https://ki-ana.at/api/me`
  - Erwartet: `{"auth":true,"user":{...}}`
  - Erwartet für Gerald: `user.is_creator: true` oder `roles` enthält `creator`/`admin`

Browser DevTools:
- Application → Cookies → `https://ki-ana.at`
  - Cookie `ki_session` vorhanden
  - Flags: `Path=/`, `HttpOnly`, `SameSite=Lax`, `Secure` (bei HTTPS)
- Network → Login Response Headers:
  - `Set-Cookie: ki_session=...; Path=/; HttpOnly; SameSite=Lax; Secure`

## 2) Chat + Explain (UI)

- URL 3: `https://ki-ana.at/app/chat`
- Sende 1 Nachricht
- Unter der KI-Antwort erscheint ein aufklappbares **Explain** (nur für `creator/admin`).

### Logout-Sichtbarkeitscheck (UI)

- In der Navbar auf **Logout** klicken
- Seite neu laden
  - Erwartung: **Login** ist wieder sichtbar

## 3) Monitoring (abgesichert, kein 404)

- BasicAuth einrichten (einmalig, auf dem Host):

```bash
sudo apt-get update && sudo apt-get install -y apache2-utils
htpasswd -c /home/kiana/ki_ana/infra/nginx/.htpasswd-ops opsadmin
docker compose -f /home/kiana/ki_ana/docker-compose.yml exec nginx nginx -s reload
```

- `https://ki-ana.at/ops/grafana/`
- `https://ki-ana.at/ops/prometheus/`

Erwartet:
- Entweder BasicAuth-Prompt oder Grafana/Prometheus UI
- Kein 404

## 4) PromQL Queries (2 Stück)

In Prometheus UI oder via API:

1. Quality Gates (10m):
   `sum(increase(ki_ana_quality_gate_total[10m])) by (gate,mode)`

2. Traffic RPS (5m):
   `ki_ana_quality_traffic_rps_5m`

## Ops-Curl Snippets

Cookie/Session (Header prüfen):

```bash
curl -i -sS https://ki-ana.at/api/login \
  -H 'Content-Type: application/json' \
  --data '{"username":"gerald","password":"***"}' | sed -n '1,30p'

curl -sS https://ki-ana.at/api/me -b 'ki_session=PASTE_COOKIE' | jq
```

nginx reload + smoke:

```bash
nginx -t && systemctl reload nginx
curl -I https://ki-ana.at/static/chat.html
curl -I https://ki-ana.at/chat
curl -I https://ki-ana.at/ops/grafana/
curl -I https://ki-ana.at/ops/prometheus/

# Auth quick checks (ohne Passwörter im Log)
rm -f cookiejar.txt

# Login: nutze dein interaktives Script (siehe internes Runbook/Chat)

# Me muss auth:true
curl -sS -b cookiejar.txt https://ki-ana.at/api/me

# Logout muss per GET gehen und Cookie löschen
curl -i -sS -b cookiejar.txt -c cookiejar.txt https://ki-ana.at/api/logout | sed -n '1,30p'

# Me danach muss auth:false
curl -sS -b cookiejar.txt https://ki-ana.at/api/me
```
