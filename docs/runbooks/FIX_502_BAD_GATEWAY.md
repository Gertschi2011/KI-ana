sudo certbot renew --dry-run# Fix: 502 Bad Gateway on ki-ana.at

Most common cause: host nginx proxies `/app/*` to the Next.js upstream (usually `127.0.0.1:23100`) but the frontend process/container is not listening.

Note: don’t copy commands that contain Markdown links (e.g. `-f [docker-compose.production.yml](...)`). The shell treats `[` and `(` specially and you’ll get `bash: syntax error near unexpected token '('`. Always run the plain command: `-f docker-compose.production.yml`.

## 1) Identify which upstream is failing

On the server:

```bash
sudo tail -n 200 /var/log/nginx/error.log
sudo nginx -T | sed -n '1,220p' | cat
```

If you see `connect() failed (111: Connection refused)` for `127.0.0.1:23100`, the frontend is down.

If you see requests like `/openapi.json`, `/docs`, `/redoc` also being proxied to `127.0.0.1:23100`, nginx is routing those to the wrong upstream. Re-apply the nginx vhost patch in step 5.

## 2) Check if the frontend port is listening

```bash
sudo ss -lntp | grep -E ':23100\b' || true
```

If nothing is listening: restart the Next frontend.

## 3) If you run the frontend via Docker Compose (recommended)

From the repo root (on the server):

```bash
cd ~/ki_ana
sudo docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' | grep -E 'kiana-frontend|23100' || true
sudo docker logs --tail=200 kiana-frontend || true

# rebuild + restart frontend
sudo docker compose -f docker-compose.production.yml up -d --build kiana-frontend

# quick check
curl -sS -I http://127.0.0.1:23100/ | head -n 10
curl -sS -I https://ki-ana.at/app/chat | head -n 10
```

If the container is restarting/crashing, inspect logs and ensure the image builds successfully.

## 4) If you run the frontend as a systemd service

```bash
sudo systemctl status kiana-frontend --no-pager || true
sudo journalctl -u kiana-frontend -n 200 --no-pager || true
sudo systemctl restart kiana-frontend
```

## 5) Re-apply the nginx vhost patch (if needed)

If nginx points to the wrong upstream ports, re-apply:

```bash
cd ~/ki_ana
bash ops/runbooks/scripts/apply_nginx_patch_ki_ana_at.sh
```

Then verify:

```bash
curl -sS -I https://ki-ana.at/openapi.json | head -n 10
curl -sS -I https://ki-ana.at/docs | head -n 10
curl -sS -I https://ki-ana.at/redoc | head -n 10
curl -sS -I https://ki-ana.at/app/chat | head -n 10
```

## 6) Fix: `/static/...` permission denied (optional)

If nginx logs show errors like:

`open() "/home/kiana/ki_ana/netapi/static/fonts/..." failed (13: Permission denied)`

Then the static directory is not readable by nginx (often `www-data`). Make it readable:

```bash
cd ~/ki_ana
sudo find netapi/static -type d -exec chmod 755 {} +
sudo find netapi/static -type f -exec chmod 644 {} +
```

Then re-check:

```bash
curl -sS -I https://ki-ana.at/static/styles.css | head -n 10
```
