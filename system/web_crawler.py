#!/usr/bin/env python3
import os, sys, json, time, hashlib, re
from pathlib import Path
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup

# === Pfade ===
BASE_DIR = Path.home() / "ki_ana"
MEM_LONG = BASE_DIR / "memory" / "long_term"
SYSTEM_DIR = BASE_DIR / "system"
GENESIS = SYSTEM_DIR / "genesis_block.json"

# === Policy/Audit Hooks ===
from privacy_enforcer import redact_text
from exec_policy_guard import check_network_domain, check_resource_limits
from rate_limit_guard import allow as ratelimit_allow
from provenance_append import append_event
from crawler_filter_cache import should_fetch, content_seen, record_fetch, vacuum_if_needed
from thought_logger import log_decision

# === HTTP Config aus Policies laden ===
import json as _json
EXEC_POL = _json.loads((SYSTEM_DIR / "policies" / "exec_policy.json").read_text(encoding="utf-8"))

UA = EXEC_POL["network"]["user_agent"]
TIMEOUT = EXEC_POL["network"]["timeout_sec"]
RETRIES = EXEC_POL["network"]["max_retries"]

def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def get_url_from_stdin_or_arg():
    if len(sys.argv) >= 2 and sys.argv[1].startswith("http"):
        return sys.argv[1]
    print("🔗 Bitte gib eine URL ein:", end=" ")
    url = sys.stdin.readline().strip()
    return url

def load_genesis_ethics():
    if not GENESIS.exists():
        return []
    try:
        data = json.loads(GENESIS.read_text(encoding="utf-8"))
        return data.get("ethics", [])
    except Exception:
        return []

def ethics_check(text: str, ethics: list[str]) -> list[str]:
    # Sehr simple Heuristik: wir prüfen nur Sperrbegriffe aus Genesis; du kannst hier mehr Logik ergänzen.
    # Aktuell: niemals töten / Gewalt propagieren
    hits = []
    bad_patterns = [
        r"\b(töten|toeten|kill(en)?|ermorden)\b",
        r"\b(gewalt|anschlag|bombenbau)\b"
    ]
    low = text.lower()
    for pat in bad_patterns:
        if re.search(pat, low):
            hits.append(pat)
    return hits

def http_get_with_retries(url: str) -> requests.Response:
    headers = {"User-Agent": UA}
    last_exc = None
    for attempt in range(1, RETRIES+1):
        try:
            resp = requests.get(url, headers=headers, timeout=TIMEOUT)
            if resp.status_code == 200:
                return resp
            last_exc = Exception(f"HTTP {resp.status_code}")
        except Exception as e:
            last_exc = e
        time.sleep(1.0)
    raise last_exc or Exception("HTTP failed")

def main():
    url = get_url_from_stdin_or_arg()
    if not url:
        print("⛔ Keine URL erhalten.")
        sys.exit(1)

    # === Cache: URL TTL check ===
    if not should_fetch(url, ttl_days=7):
        print("🗂️  Cache: URL wurde kürzlich gecrawlt – überspringe.")
        try:
            log_decision(component="crawler", action="fetch", input_ref=url, outcome="skipped", reasons="ttl_recent", meta={"ttl_days": 7})
        except Exception:
            pass
        sys.exit(0)

    # === Exec-Policy: Domain erlaubt? Ressource ok? Rate-Limit ok? ===
    domain = urlparse(url).netloc
    if not check_network_domain(domain):
        print(f"⛔ Domain nicht erlaubt: {domain}")
        try:
            log_decision(component="crawler", action="domain_check", input_ref=url, outcome="denied", reasons="domain_not_allowed", meta={"domain": domain})
        except Exception:
            pass
        sys.exit(2)
    if not ratelimit_allow("crawl", domain):
        print("⏳ Rate-Limit erreicht – bitte später nochmal.")
        try:
            log_decision(component="crawler", action="rate_limit", input_ref=url, outcome="deferred", reasons="rate_limit", meta={"domain": domain})
        except Exception:
            pass
        sys.exit(3)
    if not check_resource_limits():
        print("⛔ Ressourcenlimit (CPU/Mem) überschritten, Crawl abgebrochen.")
        try:
            log_decision(component="crawler", action="resource_check", input_ref=url, outcome="aborted", reasons="resource_limits")
        except Exception:
            pass
        sys.exit(4)

    print(f"🔗 Crawler startet: {url}\n")

    # === Seite holen ===
    resp = http_get_with_retries(url)
    html = resp.text

    # === Privacy-Redaction ===
    redacted_html = redact_text(html, source_domain=domain)

    # === Inhalt extrahieren (Basic) ===
    soup = BeautifulSoup(redacted_html, "lxml")
    # Versuch, den Haupttext zu extrahieren – simpel:
    for script in soup(["script", "style", "noscript"]):
        script.decompose()
    text = soup.get_text(separator="\n")
    text = re.sub(r"\n{2,}", "\n", text).strip()
    # Seitentitel (falls vorhanden)
    try:
        page_title = (soup.title.string or "").strip()
    except Exception:
        page_title = ""

    # === Cache: Content dedup check ===
    text_hash = sha256_bytes(text.encode("utf-8"))
    if content_seen(text_hash, ttl_days=None):
        print("🗂️  Cache: Identischer Inhalt bereits vorhanden – überspringe Speichern.")
        record_fetch(url, text_hash)
        try:
            log_decision(component="crawler", action="store", input_ref=url, outcome="skipped", reasons="duplicate_content", meta={"content_sha256": text_hash})
        except Exception:
            pass
        vacuum_if_needed()
        sys.exit(0)

    # === Ethik-Check ===
    ethics = load_genesis_ethics()
    conflicts = ethics_check(text, ethics)
    print("\n🧠 Ethik-Check gegen Genesis-Block...")
    if conflicts:
        print(f"⛔ Ethische Konflikte erkannt ({len(conflicts)}): {conflicts}")
        try:
            log_decision(component="crawler", action="ethics_check", input_ref=url, outcome="blocked", reasons="ethics_conflict", meta={"conflicts": conflicts})
        except Exception:
            pass
        sys.exit(5)
    print("✅ Keine ethischen Konflikte erkannt.")

    # === Speichern ===
    MEM_LONG.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
        "source": url,
        "content": text,
        "type": "web_crawl",
        # Zusätzliche Felder für Förderung/Provenienz
        "content_sha256": text_hash,
        "title": page_title,
        "domain": domain
    }
    data_bytes = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    h = sha256_bytes(data_bytes)
    out = MEM_LONG / f"{h}.json"
    out.write_bytes(data_bytes)
    # Cache record
    record_fetch(url, text_hash)
    try:
        log_decision(component="crawler", action="store", input_ref=url, outcome="saved", reasons="new_content", meta={"file": str(out), "content_sha256": text_hash})
    except Exception:
        pass

    print(f"🌍 Crawl gespeichert: {out}")
    print(f"SHA256 Hash: {h}")

    # === Provenance-Event ===
    append_event({
        "type": "crawl_store",
        "url": url,
        "domain": domain,
        "memory_path": str(out),
        "content_sha256": h
    })

    # Optional maintenance
    vacuum_if_needed()

if __name__ == "__main__":
    main()
