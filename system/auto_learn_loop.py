#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os, re, json, time, hashlib, subprocess, shutil
from pathlib import Path
from datetime import datetime
from urllib.parse import quote

# ===== Pfade =====
BASE      = Path.home() / "ki_ana"
MEM       = BASE / "memory"
LONGTERM  = MEM / "long_term"
TO_LEARN  = MEM / "to_learn.txt"
TOPIC_IDX = MEM / "topic_index.json"
REFLECT   = BASE / "learning" / "reflections"
SYSTEM    = BASE / "system"
WEB_CRAWL = SYSTEM / "web_crawler.py"
CHAIN_W   = SYSTEM / "chain_writer.py"

# ===== Personality Hooks =====
# (vorhanden aus deinem Projekt)
from personality_engine import rank_sources, register_feedback, bump_curiosity

# ===== Bootstrap (Basis-Ordner/Dateien legt die Repair-Funktion an) =====
ARTIKEL = {"ein","eine","einen","einem","einer","der","die","das","den","dem","des"}

# ===== Utils =====
def now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"

def normalize_topic(t: str) -> str:
    t = " ".join(t.strip().lower().split())
    parts = [p for p in t.split() if p]
    while parts and parts[0] in ARTIKEL:
        parts = parts[1:]
    return " ".join(parts)

def read_to_learn() -> list[str]:
    raw = TO_LEARN.read_text(encoding="utf-8")
    raw = raw.replace("\r\n", "\n").replace("\r", "\n")
    return [l.strip() for l in raw.splitlines() if l.strip()]

def write_to_learn(lines: list[str]) -> None:
    TO_LEARN.write_text(("\n".join(lines) + ("\n" if lines else "")), encoding="utf-8")

def load_index() -> list[dict]:
    return json.loads(TOPIC_IDX.read_text(encoding="utf-8"))

def save_index(idx: list[dict]) -> None:
    TOPIC_IDX.write_text(json.dumps(idx, indent=2, ensure_ascii=False), encoding="utf-8")

def index_add(topic: str, path: Path, source: str, ts: str) -> None:
    idx = load_index()
    idx.append({"topic": normalize_topic(topic), "path": str(path), "source": source, "timestamp": ts})
    save_index(idx)

def summarize(text: str, max_sentences: int = 3, max_chars: int = 800) -> str:
    parts = re.split(r'(?<=[.!?])\s+', re.sub(r'\s+', ' ', text).strip())
    s = " ".join(parts[:max_sentences]).strip()
    if len(s) > max_chars:
        s = s[:max_chars].rsplit(" ", 1)[0] + " ..."
    return s

def latest_memory_block() -> Path | None:
    files = sorted(LONGTERM.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None

# ===== Environment-Repair / Checks =====
def ensure_dirs_and_files():
    """Erzeugt benötigte Ordner/Dateien, wenn sie fehlen."""
    MEM.mkdir(parents=True, exist_ok=True)
    LONGTERM.mkdir(parents=True, exist_ok=True)
    REFLECT.mkdir(parents=True, exist_ok=True)
    if not TO_LEARN.exists():
        TO_LEARN.write_text("", encoding="utf-8")
    if not TOPIC_IDX.exists():
        TOPIC_IDX.write_text("[]", encoding="utf-8")

def check_python_executable():
    exe = sys.executable
    ok = Path(exe).exists()
    return ok, exe

def check_system_scripts():
    missing = []
    if not WEB_CRAWL.exists():
        missing.append(str(WEB_CRAWL))
    if not CHAIN_W.exists():
        # Chain-Writer ist optional; wir warnen nur
        print(f"ℹ️ Hinweis: {CHAIN_W} fehlt. Chain-Events werden übersprungen.")
    return missing

def check_write_permissions():
    problems = []
    for p in (LONGTERM, REFLECT, MEM):
        try:
            testfile = p / ".write_test"
            testfile.write_text("ok", encoding="utf-8")
            testfile.unlink(missing_ok=True)
        except Exception as e:
            problems.append((str(p), str(e)))
    return problems

def environment_repair() -> tuple[bool, list[str]]:
    """Führt Checks aus und repariert, wo möglich. Gibt (ok, warnings) zurück."""
    warnings: list[str] = []

    # 1) Ordner/Dateien sicherstellen
    ensure_dirs_and_files()

    # 2) Python/venv prüfen
    ok_py, exe = check_python_executable()
    if not ok_py:
        warnings.append(f"Python-Interpreter nicht gefunden: {exe}")

    # 3) Systemskripte vorhanden?
    missing = check_system_scripts()
    if missing:
        for m in missing:
            warnings.append(f"❌ Systemskript fehlt: {m}")
        # Ohne WEB_CRAWL können wir nicht lernen
        return False, warnings

    # 4) Schreibrechte testen
    perm_issues = check_write_permissions()
    if perm_issues:
        for path, err in perm_issues:
            warnings.append(f"Schreibproblem in {path}: {err}")
        return False, warnings

    # 5) Sanity Queue/Index
    try:
        raw = TO_LEARN.read_text(encoding="utf-8")
        TO_LEARN.write_text(raw.replace("\r\n", "\n").replace("\r", "\n"), encoding="utf-8")
    except Exception as e:
        warnings.append(f"to_learn.txt nicht lesbar: {e}")

    try:
        data = json.loads(TOPIC_IDX.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError("topic_index.json ist kein Array – setze auf [].")
    except Exception as e:
        warnings.append(f"topic_index.json defekt oder leer – neu initialisiert: {e}")
        TOPIC_IDX.write_text("[]", encoding="utf-8")

    return True, warnings

# ===== Crawling & Chain =====
def crawl_url(url: str) -> dict | None:
    """
    Ruft den bestehenden web_crawler.py auf (Policies/Privacy/Audit),
    parst stdout und extrahiert 'Crawl gespeichert:' und 'SHA256 Hash:'.
    """
    try:
        res = subprocess.run(
            [sys.executable, str(WEB_CRAWL)],   # venv-sicher
            input=f"{url}\n",
            text=True,
            capture_output=True,
            timeout=180
        )
    except Exception as e:
        print(f"⚠️ Crawler-Start fehlgeschlagen: {e}")
        return None

    out = (res.stdout or "") + "\n" + (res.stderr or "")
    m_path = re.search(r"Crawl gespeichert:\s*(.+\.json)", out)
    m_hash = re.search(r"SHA256 Hash:\s*([0-9a-f]{64})", out)
    if m_path and m_hash and Path(m_path.group(1)).exists():
        return {"path": Path(m_path.group(1)), "hash": m_hash.group(1)}
    else:
        # hilfreiche Ausgabe bei Fehlern
        print(out.strip()[:2000])
        return None

def chain_write(entry_type: str, topic: str, memory_path: Path, source: str, meta: dict):
    """Defensiver Chain-Writer: nutzt venv-Python; überspringt, wenn chain_writer fehlt."""
    if not CHAIN_W.exists():
        return
    try:
        subprocess.run([
            sys.executable, str(CHAIN_W),
            "--type", entry_type,
            "--topic", topic,
            "--source", source,
            "--memory_path", str(memory_path),
            "--meta", json.dumps(meta, ensure_ascii=False)
        ], check=False)
    except Exception as e:
        print(f"⚠️ chain_writer Fehler: {e}")

def _canonical_for_hash(obj: dict) -> dict:
    d = dict(obj)
    for k in ("hash", "hash_stored", "hash_calc"):
        d.pop(k, None)
    return d

def _calc_hash(obj: dict) -> str:
    raw = json.dumps(_canonical_for_hash(obj), sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()

def make_summary_block(topic: str, source_url: str, source_mem_path: Path) -> Path:
    data = json.loads(source_mem_path.read_text(encoding="utf-8"))
    text = data.get("content","")
    summary = summarize(text)
    block = {
        "type": "summary",
        "topic": normalize_topic(topic),
        "content": summary,
        "timestamp": now_iso(),
        "source": source_url,
        "derived_from": str(source_mem_path)
    }
    # attach deterministic hash field used by viewers/validators
    block["hash"] = _calc_hash(block)
    b = json.dumps(block, ensure_ascii=False, indent=2).encode("utf-8")
    name = hashlib.sha256(b).hexdigest() + ".json"
    out = LONGTERM / name
    out.write_bytes(b)
    return out

def reflect_learning(topic: str, urls: list[str], ok: bool, note: str):
    ref = {
        "timestamp": now_iso(),
        "topic": normalize_topic(topic),
        "urls": urls,
        "success": ok,
        "note": note
    }
    name = hashlib.sha256(json.dumps(ref, sort_keys=True, ensure_ascii=False).encode()).hexdigest()+".json"
    (REFLECT / name).write_text(json.dumps(ref, indent=2, ensure_ascii=False), encoding="utf-8")

def candidate_urls(topic: str) -> list[str]:
    t = normalize_topic(topic)
    urls = [
        f"https://de.wikipedia.org/wiki/{quote(t.replace(' ', '_'))}",
        f"https://en.wikipedia.org/wiki/{quote(t.replace(' ', '_'))}",
        f"https://www.britannica.com/search?query={quote(t)}"
    ]
    # Persönlichkeit: nach Präferenzen sortieren
    return rank_sources(urls)

# ===== Hauptlogik Lernen =====
def learn_topic(topic: str) -> bool:
    topic_n = normalize_topic(topic)
    bump_curiosity(topic_n, 0.02)  # Persönlichkeit: leichte Neugier am Start

    urls = candidate_urls(topic_n)
    saved = None
    used_url = None
    for url in urls:
        print(f"🌐 Versuche: {url}")
        res = crawl_url(url)
        if res:
            saved = res
            used_url = url
            break
        time.sleep(1.0)

    if not saved:
        register_feedback("failure")
        reflect_learning(topic_n, urls, False, "Kein Crawl erfolgreich")
        print(f"❌ Lernen fehlgeschlagen: {topic_n}")
        return False

    # Chain-Write: web_crawl
    chain_write("web_crawl", topic_n, saved["path"], used_url, {"url": used_url})

    # Summary erzeugen + in Chain und Index
    summary_path = make_summary_block(topic_n, used_url, saved["path"])
    index_add(topic_n, summary_path, used_url, now_iso())
    chain_write("summary", topic_n, summary_path, used_url, {"derived_from": str(saved["path"])})

    register_feedback("success")
    reflect_learning(topic_n, [used_url], True, "Crawl+Summary ok")
    print(f"✅ Gelernt: {topic_n}")
    return True

def loop_forever(sleep_sec: int = 120):
    print("♾️ Auto-Lernloop gestartet …")
    while True:
        try:
            topics = read_to_learn()
            if not topics:
                print("😴 Nichts zu lernen. Warte …")
                time.sleep(sleep_sec)
                continue

            # FIFO
            topic = topics.pop(0)
            print(f"🧠 Thema: {topic}")
            ok = learn_topic(topic)

            # Nur wieder einreihen, wenn fehlgeschlagen
            if not ok:
                topics.append(topic)
            write_to_learn(topics)

            # kurze Atempause
            time.sleep(2 if ok else sleep_sec)
        except KeyboardInterrupt:
            print("🛑 Manuell gestoppt.")
            break
        except Exception as e:
            print(f"⚠️ Fehler im Lernloop: {e}")
            time.sleep(sleep_sec)

# ===== Start =====
if __name__ == "__main__":
    ok, warns = environment_repair()
    for w in warns:
        print("🛠️", w)
    if not ok:
        print("⛔ Umgebung fehlerhaft – Auto-Learn wird beendet.")
        sys.exit(2)

    loop_forever(120)  # alle 2 Minuten prüfen
