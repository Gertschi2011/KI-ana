# One-Command Deploy + Smoke (prod/staging)

Ziel: **ein Befehl** → rebuild → recreate → (optional) nginx reload → Smoke (Health + /api/me + SSE) → **OK/FAIL**.

## Voraussetzungen

- Repo liegt auf dem Server unter `/home/kiana/ki_ana`
- Docker + Compose Plugin sind installiert (`docker compose version`)
- Für SSE-Smoketest brauchst du einen User/Pass (creator/admin empfohlen)

## Staging

```bash
cd /home/kiana/ki_ana
./scripts/deploy_and_smoke.sh --env staging --service all
```

Nur Smoke (ohne build/recreate):

```bash
./scripts/deploy_and_smoke.sh --env staging --smoke-only
```

## Prod

```bash
cd /home/kiana/ki_ana
./scripts/deploy_and_smoke.sh --env prod --service frontend
```

Wenn nginx-Konfig/vhost angepasst wurde:

```bash
./scripts/deploy_and_smoke.sh --env prod --service all --reload-nginx
```

## Wrapper (optional)

```bash
./scripts/deploy_and_smoke_prod.sh --service all
./scripts/deploy_and_smoke_staging.sh --service all
```

## Was wird geprüft?

- `GET https://ki-ana.at/health` (stabiler Health-Endpoint)
- `GET https://ki-ana.at/api/me` → `.auth` wird ausgegeben
- `scripts/smoke_sse_twice_browserlike.sh`:
  - Login via `/api/login`
  - `/api/me` muss `auth:true` sein
  - 2× Stream: mindestens ein `data:` und mindestens ein Finalize-Frame

Bei Fail:
- Script gibt die letzten 30 Zeilen der Fehl-Stufe aus
- Danach eine „Next action“-Empfehlung (Compose logs)
