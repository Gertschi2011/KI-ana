# KI_ana Knowledge Prune Runbook

This runbook covers lifecycle management for Knowledge Blocks (TTL pruning) and verification steps.

## Environment
- `KI_KNOWLEDGE_TTL_DAYS` (default: 365)
  Controls the maximum age of knowledge blocks. Blocks older than `N` days are deleted by the prune job.

## Manual Prune
```bash
cd /home/kiana/ki_ana
python3 system/knowledge_prune.py --days ${KI_KNOWLEDGE_TTL_DAYS:-365}
```

## Systemd Service & Timer
Files are provided under `deploy/systemd/`:
- `kiana-knowledge-prune.service`
- `kiana-knowledge-prune.timer`

### Install and Enable
```bash
sudo cp ki_ana/deploy/systemd/kiana-knowledge-prune.* /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now kiana-knowledge-prune.timer
```

### Verify Timer
```bash
systemctl list-timers | grep kiana-knowledge-prune
journalctl -u kiana-knowledge-prune.service -n 100 --no-pager
```

### Run On-Demand
```bash
sudo systemctl start kiana-knowledge-prune.service
```

## Troubleshooting
- Ensure Python path and working directory are correct in the service file (`/home/kiana/ki_ana`).
- Verify the database is reachable and migrations/tables exist (`init_db()` runs within the script).
- Check `.env` loading by the API (the prune script does not require API to run, but shares the same DB path via `netapi.db`).
- If pruning is too aggressive or too mild, adjust `KI_KNOWLEDGE_TTL_DAYS` or provide `--days`.
