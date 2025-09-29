import os, json, subprocess, time, urllib.parse
from pathlib import Path
from datetime import datetime

# ===== Pfade =====
BASE_DIR = Path.home() / "ki_ana" / "memory"
LONG_TERM = BASE_DIR / "long_term"
OPEN_Q = BASE_DIR / "open_questions.json"
TO_LEARN = BASE_DIR / "to_learn.txt"
TOPIC_INDEX = BASE_DIR / "topic_index.json"

WEB_CRAWLER = Path.home() / "ki_ana" / "system" / "web_crawler.py"
CHAIN_WRITER = Path.home() / "ki_ana" / "system" / "chain_writer.py"

# ===== Bootstrap =====
BASE_DIR.mkdir(parents=True, exist_ok=True)
LONG_TERM.mkdir(parents=True, exist_ok=True)
if not OPEN_Q.exists():
    OPEN_Q.write_text("{}", encoding="utf-8")
if not TOPIC_INDEX.exists():
    TOPIC_INDEX.write_text("[]", encoding="utf-8")
if not TO_LEARN.exists():
    TO_LEARN.write_text("", encoding="utf-8")

ARTIKEL = {"ein","eine","einen","einem","einer","der","die","das","den","dem","des"}

# ===== Helpers =====
def normalize_topic(topic: str) -> str:
    t = " ".join(topic.strip().lower().split())
    # führende Artikel entfernen
    parts = [p for p in t.split() if p]
    while parts and parts[0] in ARTIKEL:
        parts = parts[1:]
    return " ".join(parts).strip()

def load_open_q():
    return json.loads(OPEN_Q.read_text(encoding="utf-8"))

def save_open_q(d):
    OPEN_Q.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")

def pop_to_learn():
    lines = [l.strip() for l in TO_LEARN.read_text(encoding="utf-8").splitlines() if l.strip()]
    if not lines:
        return None
    topic = lines[0]
    TO_LEARN.write_text("\n".join(lines[1:]) + ("\n" if len(lines) > 1 else ""), encoding="utf-8")
    return topic

def latest_memory_block():
    files = sorted(LONG_TERM.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None

def load_topic_index():
    return json.loads(TOPIC_INDEX.read_text(encoding="utf-8"))

def save_topic_index(idx):
    TOPIC_INDEX.write_text(json.dumps(idx, indent=2, ensure_ascii=False), encoding="utf-8")

def index_add(topic, memory_path, source, ts):
    idx = load_topic_index()
    idx.append({
        "topic": normalize_topic(topic),
        "path": str(memory_path),
        "source": source,
        "timestamp": ts
    })
    save_topic_index(idx)

def topic_already_indexed(topic: str) -> bool:
    t = normalize_topic(topic)
    for e in load_topic_index():
        et = e.get("topic","")
        if et == t or et.startswith(t) or t in et:
            return True
    return False

def wikipedia_url(topic):
    t = normalize_topic(topic).replace(" ", "_")
    return f"https://de.wikipedia.org/wiki/{urllib.parse.quote(t)}"

def run_crawler_interactive(url: str, retries: int = 2, delay: float = 1.5) -> bool:
    """
    Führt web_crawler.py aus, übergibt URL via stdin. Bei Fehlern einfacher Retry.
    """
    for attempt in range(1, retries+1):
        print(f"   ▶️ Crawler-Start (Versuch {attempt}/{retries}) …")
        try:
            res = subprocess.run(
                ["python3", str(WEB_CRAWLER)],
                input=f"{url}\n",
                text=True,
                capture_output=True,
                timeout=120
            )
            # Log-Ausgabe zur Diagnose
            stdout, stderr = res.stdout, res.stderr
            if stdout:
                print(stdout.strip()[:8000])  # begrenzen, damit es nicht ausufert
            if res.returncode == 0:
                return True
            else:
                print(f"   ⚠️ Crawler-Exitcode {res.returncode}")
                if stderr:
                    print(f"   ⚠️ stderr: {stderr.strip()[:2000]}")
        except subprocess.TimeoutExpired:
            print("   ⏳ Crawler-Timeout.")
        time.sleep(delay)
    return False

def chain_write(entry_type: str, topic: str, memory_path: Path, source: str, meta: dict):
    subprocess.run([
        "python3", str(CHAIN_WRITER),
        "--type", entry_type,
        "--topic", normalize_topic(topic),
        "--source", source,
        "--memory_path", str(memory_path),
        "--meta", json.dumps(meta)
    ])

def crawl_and_chain(topic, url):
    topic_norm = normalize_topic(topic)
    print(f"🌐 CRAWL: {topic_norm} → {url}")

    ok = run_crawler_interactive(url)
    if not ok:
        print("⚠️ Crawler fehlgeschlagen (nach Retries).")
        return False

    latest = latest_memory_block()
    if not latest:
        print("⚠️ Kein neuer Memory-Block gefunden.")
        return False

    # Memory JSON lesen
    try:
        data = json.loads(latest.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"⚠️ Konnte Memory-Block nicht lesen: {e}")
        return False

    ts = data.get("timestamp", datetime.utcnow().isoformat()+"Z")
    src = data.get("source", url)

    # Index aktualisieren + Chain-Block schreiben
    index_add(topic_norm, latest, src, ts)
    chain_write("web_crawl", topic_norm, latest, src, {"url": url})

    print(f"✅ Fertig: {topic_norm}")
    return True

# ===== Ein Durchlauf =====
def loop_once():
    # 1) Offene Fragen priorisieren
    oq = load_open_q()
    if oq:
        topic = list(oq.keys())[0]  # FIFO
        topic_norm = normalize_topic(topic)
        if topic_already_indexed(topic_norm):
            # schon erledigt → aus offenen Fragen entfernen
            del oq[topic]
            save_open_q(oq)
            print(f"ℹ️ Offene Frage '{topic_norm}' war schon gelernt → bereinigt.")
            return True
        url = wikipedia_url(topic_norm)
        ok = crawl_and_chain(topic_norm, url)
        if ok:
            del oq[topic]
            save_open_q(oq)
            return True

    # 2) Danach To-Learn-Liste
    t = pop_to_learn()
    if t:
        topic_norm = normalize_topic(t)
        if topic_already_indexed(topic_norm):
            print(f"ℹ️ Überspringe '{topic_norm}' (bereits im Index).")
            return True
        url = wikipedia_url(topic_norm)
        crawl_and_chain(topic_norm, url)
        return True

    print("😴 Nichts zu tun (keine offenen Fragen, keine To-Learn-Einträge).")
    return False

if __name__ == "__main__":
    print("🤖 KI_ana Agent-Loop gestartet (ein Durchlauf).")
    loop_once()
