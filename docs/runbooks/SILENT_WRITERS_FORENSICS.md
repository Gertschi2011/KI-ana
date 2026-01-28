# Silent Writers — Forensics Runbook (Filesystem Writes)

Ziel: Bei jeder Dateiänderung in `memory/long_term/blocks` sofort sehen:
- **was** geschrieben wurde (Pfad + Event)
- **ob** es valide ist (Size + JSON parse)
- **wer** geschrieben hat (PID/Commandline + Container-Hinweis)

## One-liner (empfohlen)

Der Helper kombiniert `inotifywait` + Attribution + Integritätschecks:
- Bei **OPEN**: nur Attribution (`lsof`/`fuser` + PID→cgroup→Docker-Hinweis)
- Bei **CLOSE_WRITE/MOVED_TO**: nur Integrität (`stat` + JSON-Parse)

Damit bekommst du maximale Trefferquote für „wer schreibt“ ohne False-Positives durch halbgeschriebene JSONs.

```bash
./tools/forensics/watch_blocks.sh /home/kiana/ki_ana/memory/long_term/blocks
```

Hinweise:
- Für vollständige Attribution (lsof/fuser) wird meist `sudo` gebraucht.
- Dependency: `inotifywait` (Paket häufig: `inotify-tools`).

## LiveLog Producer (empfohlen für dauerhafte Sichtbarkeit)

Für ein dauerhaftes "LiveLog" (SSE/UI) brauchst du einen Producer, der Events ins Backend einspeist.
Der Producer läuft **separat** (kein Einfluss auf Backend-Request-Path) und darf optional `sudo` nutzen.

Tool:

```bash
python3 tools/livelog/producer_blocks.py /home/kiana/ki_ana/memory/long_term/blocks \
	--base-url https://ki-ana.at \
	--token "$ADMIN_API_TOKEN" \
	--use-sudo
```

Auth-Optionen:
- `--token` (Bearer Creator/Admin; fallback: env `ADMIN_API_TOKEN`)
- `--cookie "ki_session=..."` oder `--cookie-jar /path/to/cookiejar.txt` (alias: `--cookiejar`)

Events:
- Bei **OPEN**: Attribution (PID/Commandline/Container-Hint)
- Bei **CLOSE_WRITE/MOVED_TO**: `stat` + JSON-Parse (Integrität)

## Manuell (2-Terminal Workflow)

Terminal A (Watch):

```bash
inotifywait -m -e open,create,close_write,move --format '%T %e %w%f' --timefmt '%F %T' /home/kiana/ki_ana/memory/long_term/blocks
```

Terminal B (Wer schreibt?):

```bash
FILE="/home/kiana/ki_ana/memory/long_term/blocks/BLK_XXXX.json"
sudo lsof -n -- "$FILE" 2>/dev/null || true
sudo fuser -v "$FILE" 2>/dev/null || true

PID=<pid-aus-lsof>
ps -fp "$PID"
cat /proc/"$PID"/cgroup | sed -n '1,5p'
```

Integrity Spotcheck:

```bash
stat -c 'size=%s mtime=%y owner=%U:%G mode=%a' "$FILE"
python3 -c 'import json,sys; json.load(open(sys.argv[1])); print("json:ok")' "$FILE"
```

## CLI Tools Safety (Mirror / Memory Compression)

Die Tools wurden so gehärtet, dass sie **standardmäßig read-only/dry-run** laufen.

- `--write` aktiviert Schreibzugriffe.
- `--memory-dir` ist **required** wenn `--write` gesetzt ist (gegen "silent writes" in falsche Pfade).
- Root-Guard: als root wird abgebrochen, außer `--allow-root`.

Beispiele:

```bash
# Mirror dry-run (keine Writes)
python3 tools/mirror.py --topic CVE

# Mirror write (expliziter Memory-Pfad)
python3 tools/mirror.py --topic CVE --write --memory-dir /home/kiana/ki_ana/memory

# Compression dry-run
python3 tools/memory_compression.py --age-days 60 --min-entries 100

# Compression write (erst jetzt werden Experiences geschrieben + Entries archiviert)
python3 tools/memory_compression.py --age-days 60 --min-entries 100 --write --memory-dir /home/kiana/ki_ana/memory
```
