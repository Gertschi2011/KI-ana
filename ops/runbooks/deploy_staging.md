# Staging Deploy Cheatsheet (idiotensicher)

Ziel: Änderungen an Frontend/Backend **wirklich live** bekommen (Staging Stack), ohne in die falschen Images/Container zu deployen.

## 0) Immer der gleiche Compose-Prefix

**Immer** diese beiden Flags verwenden:

- `-p ki_ana_staging`
- `-f docker-compose.staging.yml`

Wenn du das vergisst, baust du am Ende `ki_ana-*` statt `ki_ana_staging-*` und wunderst dich, warum „live“ nichts ändert.

## 1) Bin ich im richtigen Stack?

```bash
docker compose -p ki_ana_staging -f docker-compose.staging.yml ps
```

Erwartung:
- `ki_ana_staging-frontend-1` läuft (Port `23000->3000`)
- `ki_ana_staging-backend-1` läuft (Port `28000->8000`)

## 2) Frontend rebuild + recreate

```bash
cd /home/kiana/ki_ana

docker compose -p ki_ana_staging -f docker-compose.staging.yml build frontend

docker compose -p ki_ana_staging -f docker-compose.staging.yml up -d \
  --no-deps --force-recreate frontend
```

## 3) Backend rebuild + recreate

```bash
cd /home/kiana/ki_ana

docker compose -p ki_ana_staging -f docker-compose.staging.yml build backend

docker compose -p ki_ana_staging -f docker-compose.staging.yml up -d \
  --no-deps --force-recreate backend
```

## 4) Nginx reload (Host)

```bash
sudo nginx -t && sudo systemctl reload nginx
```

## 5) Quick Smoke Checks (live)

### „Hab ich die richtige UI live?“

```bash
curl -I https://ki-ana.at/app/chat | head
```

### „Auth stimmt?“

```bash
curl -sS https://ki-ana.at/api/me
```

### „Logout Endpoint ok (Runbook-kompatibel)?“

`/api/logout` muss **GET** können und Cookie-Clears setzen.

```bash
curl -i -sS https://ki-ana.at/api/logout | sed -n '1,30p'
```

## 6) Optional: Logs / Restart verifizieren

```bash
docker compose -p ki_ana_staging -f docker-compose.staging.yml logs --tail=100 frontend
docker compose -p ki_ana_staging -f docker-compose.staging.yml logs --tail=100 backend
```
