# brain.py – smarter think(): Intents, Memory-RAG, Web-Fallback (robust & lazy imports)
from __future__ import annotations

import os
import re
import random
import html
from typing import Tuple, List, Dict, Optional, Callable

import json
from pathlib import Path

# --- Self-learning directories (filesystem queues) ---
_ROOT = Path(__file__).resolve().parents[1]  # /home/kiana/ki_ana
_LEARN_DIR = _ROOT / "learning"
_EXP_DIR = _LEARN_DIR / "experiments"
_TASKS_PENDING = _EXP_DIR / "pending"
_TASKS_DONE = _EXP_DIR / "done"
_BRAIN_MOD_DIR = _LEARN_DIR / "brain_modules"

# --- utility: clean any HTML/JS noise from fetched web text ---
def _clean_text(txt: str) -> str:
    """
    Remove HTML tags / scripts, collapse whitespace, and unescape HTML entities.
    Designed for very noisy sources (e.g., Wikipedia page HTML).
    """
    if not isinstance(txt, str):
        return ""
    # strip tags
    txt = re.sub(r"<[^>]+>", " ", txt)
    # strip leftover JS/CSS artifacts like 'var foo=...' that sometimes leak into summaries
    txt = re.sub(r"\b(var|let|const)\s+[A-Za-z_$][\w$]*\s*=\s*[^;]+;", " ", txt)
    # collapse whitespace
    txt = re.sub(r"\s+", " ", txt)
    # unescape entities
    txt = html.unescape(txt)
    return txt.strip()

def _ensure_learning_dirs():
    for d in (_LEARN_DIR, _EXP_DIR, _TASKS_PENDING, _TASKS_DONE, _BRAIN_MOD_DIR):
        d.mkdir(parents=True, exist_ok=True)

# -----------------------------------------------------------------------------
# Lazy module access for memory_store and web_qa
# -----------------------------------------------------------------------------
_MEM_SEARCH: Optional[Callable] = None
_MEM_GET: Optional[Callable] = None
_MEM_ADD: Optional[Callable] = None
_MEM_AUTO_REF: Optional[Callable] = None
_WEB_SUM: Optional[Callable] = None

def _lazy_wire_memory():
    global _MEM_SEARCH, _MEM_GET, _MEM_ADD, _MEM_AUTO_REF
    if _MEM_SEARCH is not None:
        return
    try:
        # Local imports to avoid hard failure at module import time
        from .memory_store import search_blocks, get_block, add_block, auto_update_block  # type: ignore
        _MEM_SEARCH, _MEM_GET, _MEM_ADD, _MEM_AUTO_REF = search_blocks, get_block, add_block, auto_update_block
    except Exception:
        # Soft fallback: no memory available
        _MEM_SEARCH = lambda q, top_k=5, min_score=0.1: []            # type: ignore
        _MEM_GET = lambda bid: None                                    # type: ignore
        _MEM_ADD = lambda **kw: None                                    # type: ignore
        _MEM_AUTO_REF = lambda *a, **k: None                            # type: ignore

def _lazy_wire_web():
    global _WEB_SUM
    if _WEB_SUM is not None:
        return
    try:
        from .web_qa import web_search_and_summarize  # type: ignore
        _WEB_SUM = web_search_and_summarize
    except Exception:
        _WEB_SUM = lambda q: (None, None)                               # type: ignore

# Prefer local LLM (Ollama) if available
try:
    from .core import llm_local  # type: ignore
except Exception:  # pragma: no cover
    llm_local = None  # type: ignore

# -----------------------------------------------------------------------------
# Self-learning manager (file-based task queue)
# -----------------------------------------------------------------------------

import time

# --- idle/self-learning time bookkeeping ---
_LAST_TOUCH_FILE = _LEARN_DIR / "last_user_interaction.txt"
_LAST_IDLE_FILE  = _LEARN_DIR / "last_idle_action.txt"

# friendly digest/inbox files
_DIGEST_LAST = _LEARN_DIR / "digest_last.json"
_DIGEST_LAST_SHOWN = _LEARN_DIR / "digest_last_shown.txt"

def _read_json(path: Path) -> Optional[dict]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None

def _write_json(path: Path, data: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
    except Exception:
        pass

def _now() -> int:
    return int(time.time())

def _read_int(path: Path) -> int:
    try:
        return int(path.read_text().strip())
    except Exception:
        return 0

def _write_int(path: Path, value: int):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(str(value), encoding="utf-8")
    tmp.replace(path)

class SelfLearningManager:
    """
    Creates learn plans and queues code katas as JSON task files under:
      learning/experiments/pending/*.json

    A separate worker (e.g., system/skill_runner.py) can pick these up,
    execute tests, and write results into learning/experiments/done/.
    """
    def __init__(self):
        _ensure_learning_dirs()

    def _new_task_path(self, kind: str) -> Path:
        ts = int(time.time() * 1000)
        return _TASKS_PENDING / f"{ts}_{kind}.json"

    def create_programming_plan(self, language: str = "python") -> Dict:
        plan = {
            "kind": "learn_plan",
            "topic": f"programming_{language}",
            "created_at": int(time.time()),
            "steps": [
                {"day": 1, "title": "Hello World & Variablen", "tasks": ["print()", "Variablen", "Eingabe/Ausgabe"]},
                {"day": 2, "title": "Bedingungen", "tasks": ["if/elif/else", "Vergleiche", "Wahrheitswerte"]},
                {"day": 3, "title": "Schleifen", "tasks": ["for", "while", "range()", "Iterieren"]},
                {"day": 4, "title": "Funktionen", "tasks": ["def", "Parameter", "Rückgabewerte"]},
                {"day": 5, "title": "Listen & Dicts", "tasks": ["list", "dict", "Comprehensions"]},
                {"day": 6, "title": "Dateien & Fehler", "tasks": ["open()", "with", "try/except"]},
                {"day": 7, "title": "Mini-Projekt", "tasks": ["Konsolen-Tool", "Dokumentation", "Reflexion"]},
            ],
        }
        # store as memory block for easy recall
        try:
            _lazy_wire_memory()
            if _MEM_ADD:
                _MEM_ADD(title="Lernplan Programmieren (7 Tage)", content=json.dumps(plan, ensure_ascii=False, indent=2), tags=["plan","learn","programming"])
        except Exception:
            pass
        return plan

    def queue_code_kata(self, title: str, description: str, starter: str, tests: List[str], language: str = "python") -> Path:
        """
        Creates a kata task file the runner can execute.
        - starter: initial source code string
        - tests: list of python statements (e.g., assert ...) evaluated by the runner in a sandbox
        """
        task = {
            "kind": "code_kata",
            "language": language,
            "title": title,
            "description": description,
            "starter": starter,
            "tests": tests,
            "created_at": int(time.time()),
        }
        p = self._new_task_path("code_kata")
        p.write_text(json.dumps(task, ensure_ascii=False, indent=2), encoding="utf-8")
        return p

    def queue_research(self, query: str) -> Path:
        task = {
            "kind": "web_research",
            "query": query,
            "created_at": int(time.time()),
        }
        p = self._new_task_path("web_research")
        p.write_text(json.dumps(task, ensure_ascii=False, indent=2), encoding="utf-8")
        return p

def _maybe_digest_greeting() -> Optional[str]:
    """
    If there's a recent digest (news learned), return a single friendly line once in a while.
    We show it only if the digest is newer than the last 'shown' timestamp.
    """
    try:
        d = _read_json(_DIGEST_LAST)
        if not d:
            return None
        ts = int(d.get("ts", 0))
        last_shown = _read_int(_DIGEST_LAST_SHOWN)
        # show at most once per new digest and only if not older than 12h
        if ts <= last_shown:
            return None
        if _now() - ts > 12 * 3600:
            return None
        items = d.get("items") or []
        if not items:
            return None
        titles = [str(it.get("title") or "neuer Artikel") for it in items][:3]
        line = "Kleines Update: Ich habe heute " + ", ".join(titles) + " gelernt – magst du’s sehen?"
        # mark as shown
        _write_int(_DIGEST_LAST_SHOWN, ts)
        return line
    except Exception:
        return None

def _attach_digest(text: str) -> str:
    dl = _maybe_digest_greeting()
    return (dl + "\n\n" + text) if dl else text

# -----------------------------------------------------------------------------
# Idle self-learning scheduler
# -----------------------------------------------------------------------------
def note_user_interaction() -> None:
    """Mark the last time a human interacted with Kiana (for idle detection)."""
    try:
        _write_int(_LAST_TOUCH_FILE, _now())
    except Exception:
        pass

_TREND_SEEDS = [
    # Forschung/Tech
    "neue Quantencomputer-Ergebnisse",
    "Fortschritte bei Fusionsenergie",
    "Neues zur KI-Sicherheit und Alignment",
    "Durchbrüche in Batterietechnologie",
    "Neues aus der Neurowissenschaft",
    # Programmieren
    "Python Best Practices 2025",
    "Rust vs. C++ aktuelle Trends",
    "WebAssembly Einsatzszenarien",
    "Datenbanken: neue Indizes und Storage-Engines",
    "MLOps Pipelines State of the Art",
]

_KATA_SEEDS = [
    ("FizzBuzz (Einsteiger)",
     "Gib für Vielfache von 3 'Fizz', von 5 'Buzz' und von 15 'FizzBuzz' aus, sonst die Zahl.",
     "def fizzbuzz(n:int)->str:\n    # TODO: implementiere\n    return ''\n",
     ["assert fizzbuzz(1)=='1'",
      "assert fizzbuzz(3)=='Fizz'",
      "assert fizzbuzz(5)=='Buzz'",
      "assert fizzbuzz(15)=='FizzBuzz'"]),
    ("Listen sortieren",
     "Implementiere eine stabile Sortierung für Listen kleiner Zahlen.",
     "def mysort(xs:list[int])->list[int]:\n    # TODO: implementiere\n    return sorted(xs)\n",
     ["assert mysort([3,1,2])==[1,2,3]"]),
    ("Fakultät rekursiv",
     "Schreibe eine rekursive Funktion factorial(n).",
     "def factorial(n:int)->int:\n    # TODO\n    return 1\n",
     ["assert factorial(0)==1", "assert factorial(5)==120"]),
]

# Helper to sanitize web queries
def _sanitize_query(q: str) -> str:
    q = (q or "").strip()
    # remove common filler that hurts search quality
    q = re.sub(r"\b(please|bitte|danke|kannst du|sag mir|erkl(ä|ae)r(e|) mir)\b", " ", q, flags=re.I)
    q = re.sub(r"\s+", " ", q)
    return q[:200]

def idle_tick(force: bool=False) -> Optional[str]:
    """
    Called periodically by a worker (e.g., system/skill_runner.py).
    If there was no user interaction for IDLE_MINUTES and we haven't created
    something in the last IDLE_CREATE_EVERY_MIN minutes, enqueue either a
    web_research task or a code_kata task (bounded by IDLE_MAX_PENDING).
    Returns a human-readable summary or None.
    """
    try:
        _ensure_learning_dirs()

        idle_minutes = int(os.getenv("IDLE_MINUTES", "30"))
        min_gap_min = int(os.getenv("IDLE_CREATE_EVERY_MIN", "60"))
        max_pending = int(os.getenv("IDLE_MAX_PENDING", "5"))

        try:
            pending_count = len(list(_TASKS_PENDING.glob("*.json")))
        except Exception:
            pending_count = 0

        if pending_count >= max_pending and not force:
            return None

        last_touch = _read_int(_LAST_TOUCH_FILE)
        last_idle  = _read_int(_LAST_IDLE_FILE)
        now = _now()

        if not force:
            if last_touch and now - last_touch < idle_minutes * 60:
                return None
            if last_idle and now - last_idle < min_gap_min * 60:
                return None

        mgr = SelfLearningManager()

        if random.random() < 0.5:
            query = random.choice(_TREND_SEEDS)
            tpath = mgr.queue_research(query)
            _write_int(_LAST_IDLE_FILE, now)
            return f"web_research: {tpath.name} – {query}"
        else:
            title, desc, starter, tests = random.choice(_KATA_SEEDS)
            tpath = mgr.queue_code_kata(title=title, description=desc, starter=starter, tests=tests, language="python")
            _write_int(_LAST_IDLE_FILE, now)
            return f"code_kata: {tpath.name} – {title}"
    except Exception:
        return None

async def autonomous_tick() -> str:
    """
    Periodic self-activity:
      - pick 1–3 trending topics
      - fetch summaries via web_qa (if allowed)
      - store in memory
      - write a digest file so chat can greet the user about it
    Returns a short human-readable status line for logging.
    """
    try:
        _ensure_learning_dirs()
        _lazy_wire_web()
        _lazy_wire_memory()

        if os.getenv("ALLOW_NET") != "1" or not _WEB_SUM:
            return "autopilot: net disabled"

        k = random.randint(1, 3)
        topics = random.sample(_TREND_SEEDS, k=k)

        results = []
        for q in topics:
            try:
                summary, src = _WEB_SUM(_sanitize_query(q))
                if not summary:
                    continue
                cleaned = _clean_text(str(summary))[:2000]
                title = (src or {}).get("title") if isinstance(src, dict) else None
                url = (src or {}).get("url") if isinstance(src, dict) else None
                display_title = title or q

                bid = None
                if _MEM_ADD:
                    try:
                        bid = _MEM_ADD(
                            title=f"News: {display_title}",
                            content=cleaned,
                            tags=["auto", "news", "web"],
                            url=url,
                        )
                        if bid and _MEM_AUTO_REF:
                            try:
                                _MEM_AUTO_REF(bid)
                            except Exception:
                                pass
                    except Exception:
                        pass

                results.append({"title": display_title, "url": url, "bid": bid})
            except Exception:
                continue

        if results:
            digest_text = "Heute gelernt:\n" + "\n".join(
                f"- {r['title']}" + (f" – {r['url']}" if r.get('url') else "")
                for r in results
            )
            _write_json(_DIGEST_LAST, {"ts": _now(), "items": results, "text": digest_text})
            return f"autopilot: stored {len(results)} news item(s)"
        return "autopilot: no new findings"
    except Exception:
        return "autopilot: error"

# -----------------------------------------------------------------------------
# Intents (erweiterbar)
# -----------------------------------------------------------------------------
_INTENTS = [
    (
        "greeting",
        [r"\b(hallo|hey|hi|servus|gr(ü|ue)ß\s*dich|guten\s*(morgen|tag|abend))\b"],
        [
            "Hallo! Schön, dass du da bist. Womit legen wir los?",
            "Hey! Wie kann ich dir heute helfen?",
            "Hi! Was steht an?"
        ],
    ),
    (
        "programming_learn",
        [r"\b(programmier(en|)|programmieren\s*lernen|python\s*lernen|coding|coden)\b"],
        [
            "Gerne! Ich schlage eine 7‑Tage‑Mini‑Roadmap vor (Tag 1: Hello World, Tag 2: Variablen, Tag 3: Bedingungen …). Magst du damit starten?",
            "Lass uns mit kleinen Erfolgen beginnen. Sollen wir heute eine Mini‑Aufgabe in Python lösen und morgen darauf aufbauen?"
        ],
    ),
    (
        "quantum_basics",
        [r"\bqu(ant|)en(computer|computing)\b", r"\bqubit(s?)\b", r"\bsuperposition\b", r"\bverschr(ä|ae)nk"],
        [
            "Kurz & klar: Ein Qubit kann 0 und 1 überlagern; Verschränkung koppelt Zustände. So lassen sich bestimmte Probleme theoretisch schneller lösen. Willst du eine 5‑Punkte‑Übersicht?",
            "Quantencomputer sind keine schnelleren PCs, sondern funktionieren anders (Superposition, Verschränkung). Soll ich dir Schritt für Schritt die Grundideen zeigen?"
        ],
    ),
    (
        "plan_or_explain",
        [r"\b(plan|struktur|roadmap|zusammenfassen|erkl(ä|ae)ren|erkl(ä|ae)r(e|) mir|wie geht)\b"],
        [
            "Möchtest du, dass ich es **kurz erkläre**, **zusammenfasse** oder **einen Plan** vorschlage?",
            "Sollen wir mit einer **Übersicht** starten oder mit einem **konkreten Beispiel**?"
        ],
    ),
    (
        "self_learn_programming",
        [r"\b(lern(e|) dir|bring dir)\s+(selbst\s+)?programmieren\b", r"\bauto\s*learn\b", r"\bselbst\s*lernen\b"],
        [
            "Ich starte einen Lernplan und lege die erste Code‑Übung an. Gib mir kurz ein Thema (z. B. *Listen sortieren*), sonst nehme ich FizzBuzz.",
            "Alles klar – ich lege Plan & erste Übung an. Möchtest du Python oder eine andere Sprache?"
        ],
    ),
    (
        "web_search_direct",
        [r"\b(such(e|)|google|recherchier(e|)|finde|was sagt das internet)\b"],
        [
            "Ich schaue kurz im Web nach und fasse es dir zusammen.",
            "Sekunde – ich werfe einen Blick in aktuelle Quellen."
        ],
    ),
]

def _match_intent(msg: str) -> tuple[Optional[str], Optional[str]]:
    text = (msg or "").lower()
    for name, patterns, templates in _INTENTS:
        for p in patterns:
            try:
                if re.search(p, text):
                    return name, random.choice(templates)
            except re.error:
                continue
    return None, None

# -----------------------------------------------------------------------------
# Memory composition helpers
# -----------------------------------------------------------------------------
def _compose_from_blocks(block_ids: List[str]) -> Optional[str]:
    """Compose a short answer from up to 3 memory blocks"""
    _lazy_wire_memory()
    if not block_ids:
        return None
    chunks: List[str] = []
    used = 0
    for bid in block_ids:
        b = _MEM_GET(bid) if _MEM_GET else None
        if not b:
            continue
        title = str(b.get("title", "") or "").strip()
        content = str(b.get("content", "") or "").strip()
        if not content:
            continue
        safe_title = html.escape(title) if title else "Speicher"
        safe_content = html.escape(content)
        chunks.append(f"• {safe_title}: {safe_content}")
        used += 1
        if used >= 3:
            break
    if not chunks:
        return None
    answer = "Hier ist, was ich dazu bereits weiß:\n" + "\n".join(chunks)
    # Safety cap to keep responses compact; SSE kann stückeln
    return answer[:2000]

# -----------------------------------------------------------------------------
# Web peek
# -----------------------------------------------------------------------------
def _maybe_web_peek(query: str) -> tuple[Optional[str], Optional[Dict]]:
    """Optionaler Webblick – nur wenn ALLOW_NET=1 und Webmodul vorhanden."""
    if os.getenv("ALLOW_NET") != "1":
        return None, None
    _lazy_wire_web()
    if not _WEB_SUM:
        return None, None
    try:
        summary, src = _WEB_SUM(query)
        if not summary:
            return None, None
        # clean & compact
        cleaned = _clean_text(str(summary))
        if not cleaned:
            return None, None
        # limit length to keep chat pleasant
        cleaned = cleaned[:1800]
        title = (src or {}).get("title") if isinstance(src, dict) else None
        url = (src or {}).get("url") if isinstance(src, dict) else None
        if title:
            cleaned = f"{cleaned}\n\nQuelle: {title}"
        if url:
            cleaned = f"{cleaned}\n{url}"
        return cleaned, (src or {})
    except Exception:
        return None, None

# -----------------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------------
def think_rich(user: Dict, message: str) -> Tuple[str, List[str], Optional[Dict]]:
    """
    Liefert (answer, used_block_ids, web_source_info)
    - robust gegen fehlendes memory_store/web_qa (lazy import & graceful fallback)
    - kompaktes, freundliches Deutsch
    """
    # mark activity for idle detection
    note_user_interaction()
    msg = (message or "").strip()
    if not msg:
        return (_attach_digest("Sag mir kurz, worum es geht – dann denke ich laut mit dir 🙂."), [], None)

    intent, templ = _match_intent(msg)
    if intent:
        # Special handling: self-learning bootstrap
        if intent == "self_learn_programming":
            mgr = SelfLearningManager()
            plan = mgr.create_programming_plan(language="python")
            # pick a default kata if none specified
            topic = None
            m = re.search(r"\bzu\b\s+(.+)$", msg, re.IGNORECASE)
            if m:
                topic = m.group(1).strip()
            if not topic:
                topic = "FizzBuzz"

            if topic.lower().startswith("fizzbuzz"):
                starter = "def fizzbuzz(n:int)->str:\n    # TODO: implementiere\n    return ''\n"
                tests = [
                    "assert fizzbuzz(1)=='1'",
                    "assert fizzbuzz(3)=='Fizz'",
                    "assert fizzbuzz(5)=='Buzz'",
                    "assert fizzbuzz(15)=='FizzBuzz'",
                ]
                task_path = mgr.queue_code_kata(
                    title="FizzBuzz (Einsteiger)",
                    description="Gib für Vielfache von 3 'Fizz', von 5 'Buzz' und von 15 'FizzBuzz' aus, sonst die Zahl.",
                    starter=starter,
                    tests=tests,
                    language="python",
                )
            else:
                # generic kata scaffold
                starter = f"""# Starter für Aufgabe: {topic}
def solve(x):
    # TODO: Implementiere Lösung für: {topic}
    return x
""".strip()
                tests = [
                    "assert solve(1) is not None",
                ]
                task_path = mgr.queue_code_kata(
                    title=f"Kata: {topic}",
                    description=f"Automatisch erzeugte Übung zu: {topic}",
                    starter=starter,
                    tests=tests,
                    language="python",
                )

            msg_user = (
                "Ich habe den **7‑Tage‑Lernplan** abgelegt und eine **erste Code‑Übung** in die Warteschlange gestellt.\n"
                f"- Plan: *Lernplan Programmieren (7 Tage)* (im Gedächtnis)\n"
                f"- Aufgabe: `{task_path.name}` unter `learning/experiments/pending/`\n\n"
                "Starte den Worker `system/skill_runner.py`, damit die Übung automatisch geprüft wird.\n"
                "Sag mir gern weitere Themen, dann lege ich mehr Katas an."
            )
            return (_attach_digest(msg_user), [], None)

        # Dedicated handling for new web_search_direct intent
        if intent == "web_search_direct":
            query = _sanitize_query(msg)
            # queue a background research task for later deep-dive
            try:
                mgr = SelfLearningManager()
                mgr.queue_research(query)
            except Exception:
                pass
            # try immediate peek
            web_txt, web_src = _maybe_web_peek(query)
            if web_txt:
                # store to memory and auto-refine knowledge
                used_ids: List[str] = []
                try:
                    _lazy_wire_memory()
                    if _MEM_ADD:
                        bid = _MEM_ADD(
                            title=f"Gelernt (Web): { (web_src or {}).get('title') or query }",
                            content=_clean_text(web_txt),
                            tags=["auto","web","learn"],
                            url=(web_src or {}).get("url"),
                        )
                        if bid:
                            used_ids.append(bid)
                            if _MEM_AUTO_REF:
                                try:
                                    _MEM_AUTO_REF(bid)
                                except Exception:
                                    pass
                except Exception:
                    pass
                return (_attach_digest(web_txt), used_ids, web_src)
            # if nothing found, fall back to a polite clarification
            return (_attach_digest("Ich habe noch keine gute Quelle gefunden. Formuliere es gern noch etwas präziser oder gib mir einen Link, dann lerne ich es ein."), [], None)

        # Default: friendly response (with optional web add-on)
        if templ:
            prefix = random.choice([
                f"Okay {user.get('username','du')}. ",
                "",
                "Verstanden. "
            ])
            web_txt, web_src = _maybe_web_peek(msg)
            if web_txt:
                return (_attach_digest(prefix + templ + f"\n\n{web_txt}"), [], web_src)
            return (_attach_digest(prefix + templ), [], None)

    # 2) Speicher / RAG
    _lazy_wire_memory()
    hits = _MEM_SEARCH(msg, top_k=5, min_score=0.12) if _MEM_SEARCH else []
    used_ids = [bid for (bid, _score) in hits] if hits else []
    mem_answer = _compose_from_blocks(used_ids)
    if mem_answer and len(mem_answer) >= 80:
        follow = random.choice([
            "Möchtest du, dass ich etwas davon aktualisiere oder vertiefe?",
            "Soll ich parallel aktuelle Quellen prüfen?",
            "Willst du Beispiele dazu?"
        ])
        return (_attach_digest(f"{mem_answer}\n\n{follow}"), used_ids, None)

    # 3) Web-Fallback (Wissen lernen & ablegen)
    web_summary, web_src = _maybe_web_peek(msg)
    if web_summary:
        # im Gedächtnis ablegen (soft-fail, wenn nicht verfügbar)
        try:
            if _MEM_ADD:
                bid = _MEM_ADD(
                    title=f"Gelernt: {(web_src or {}).get('title') or 'Web-Quelle'}",
                    content=_clean_text(web_summary),
                    tags=["auto","web","learn"],
                    url=(web_src or {}).get("url"),
                )
                if bid:
                    used_ids.append(bid)
                    # versuche vorhandenes Wissen automatisch zu verfeinern (Refinement)
                    try:
                        if _MEM_AUTO_REF and bid:
                            _MEM_AUTO_REF(bid)
                    except Exception:
                        pass
        except Exception:
            pass
        follow = random.choice([
            "Wenn du willst, kann ich das Thema weiter vertiefen.",
            "Soll ich mehr Details recherchieren?",
            "Ich kann dir auch eine kurze Schritt‑für‑Schritt‑Erklärung geben."
        ])
        # begrenzen, damit Antworten angenehm bleiben
        text = web_summary[:2200]
        return (_attach_digest(f"{text}\n\n{follow}"), used_ids, web_src)

    # 4) Fallback
    return (
        _attach_digest(
            f"Ich habe dich verstanden: „{msg}“. "
            f"Möchtest du, dass ich es **kurz erkläre**, **zusammenfasse** oder einen **Plan** erstelle?"
        ),
        [],
        None,
    )

# Backward‑compatible adapter: old callers expect a plain string
def think(user: Dict, message: str) -> str:
    """
    Thin wrapper over think_rich() to keep /api/chat compatible.
    Returns only the answer text; drops used_block_ids and web_source_info.
    """
    answer, _used_block_ids, _web_source = think_rich(user, message)
    return answer

# Admin/debug helper for health snapshot
def brain_status() -> Dict[str, object]:
    """Lightweight snapshot for diagnostics."""
    try:
        _ensure_learning_dirs()
        pending = len(list(_TASKS_PENDING.glob("*.json")))
        done = len(list(_TASKS_DONE.glob("*.json")))
    except Exception:
        pending = done = 0
    # Local LLM availability
    ollama_ok = False
    ollama_model = None
    try:
        from .core import llm_local  # type: ignore
        ollama_ok = bool(getattr(llm_local, "available", lambda: False)())
        ollama_model = getattr(llm_local, "OLLAMA_MODEL", None)
    except Exception:
        pass
    # Prefer settings if available to report net access
    try:
        from .config import settings as _settings  # type: ignore
        net_ok = bool(getattr(_settings, "ALLOW_NET", True))
    except Exception:
        net_ok = (os.getenv("ALLOW_NET") == "1")

    return {
        "learning_dirs": {
            "pending": str(_TASKS_PENDING),
            "done": str(_TASKS_DONE),
            "brain_modules": str(_BRAIN_MOD_DIR),
        },
        "queue_counts": {"pending": pending, "done": done},
        "net_access": net_ok,
        "ollama": {"available": ollama_ok, "model": ollama_model},
    }

# -----------------------------------------------------------------------------
# Chat-router adapters (so netapi/modules/chat/router.py prefers this module)
# -----------------------------------------------------------------------------
def respond_to(user: str, system: str = "", lang: str = "de-DE", persona: str = "friendly") -> str:
    """
    ChatGPT‑ähnliche Antwort: bevorzugt lokales LLM (Ollama). Falls nicht
    verfügbar, fällt auf think_rich() zurück (Memory + Web‑Peek).
    """

    def _sys_prompt() -> str:
        if system and system.strip():
            return system
        base = (
            "Du bist KI_ana – freundlich, empathisch und natürlich. "
            "Antworte in klaren, menschlichen Sätzen. "
            "Wenn etwas unklar ist, stelle 1 gezielte Rückfrage. "
            "Biete Optionen nur kurz an (z. B. Erklären, Stichpunkte, Plan), aber nicht jedes Mal. "
            "Nutze bereitgestellte Notizen nur, wenn sie wirklich passen. "
            "Wenn dir Wissen fehlt, sag es offen und schlage vor, es kurz nachzuschlagen oder zu lernen."
        )
        if persona == "balanced":
            base += " Halte den Ton sachlich und gut strukturiert."
        elif persona == "creative":
            base += " Erlaube Humor, bleibe korrekt."
        return base

    # Build memory context (top 3 blocks) for LLM prompt
    mem_note = ""
    try:
        _lazy_wire_memory()
        if _MEM_SEARCH and _MEM_GET:
            hits = _MEM_SEARCH(user, top_k=3, min_score=0.12) or []
            ids = [bid for (bid, _s) in hits][:3]
            chunks: List[str] = []
            for bid in ids:
                b = _MEM_GET(bid)
                if not b:
                    continue
                title = str(b.get("title") or "").strip()
                content = str(b.get("content") or "").strip().replace("\n", " ")
                if not content:
                    continue
                snippet = content[:220].strip()
                chunks.append(f"• {title}: {snippet}")
                if len(chunks) >= 3:
                    break
            if chunks:
                mem_note = "\n\n[Relevante Notizen]\n" + "\n".join(chunks)
    except Exception:
        mem_note = ""

    # Prefer local LLM if reachable
    if llm_local is not None and getattr(llm_local, "available", lambda: False)():
        content = (user or "").strip() + (mem_note or "")
        out = llm_local.chat_once(content, system=_sys_prompt())
        if isinstance(out, str) and out.strip():
            return out.strip()

    # Fallback: RAG + optional Web Peek
    try:
        u = {"username": "user", "lang": lang, "persona": persona}
        ans, _ids, _src = think_rich(u, user)
        return (ans or "").strip()
    except Exception:
        msg = (user or "").strip()
        if len(msg) <= 2:
            return "Erzähl mir kurz, worum es geht – dann helfe ich dir gern."
        return f"Okay. Zu „{msg}“: Ich kann es kurz erklären oder eine kompakte Zusammenfassung geben – was hättest du lieber?"


async def stream_response(user: str, system: str = "", lang: str = "de-DE", persona: str = "friendly"):
    """Streaming via local LLM if available; else chunk the fallback text."""
    # Try local LLM streaming
    if llm_local is not None and getattr(llm_local, "available", lambda: False)():
        # reuse memory note from respond_to path
        try:
            _lazy_wire_memory()
            mem_note = ""
            if _MEM_SEARCH and _MEM_GET:
                hits = _MEM_SEARCH(user, top_k=3, min_score=0.12) or []
                ids = [bid for (bid, _s) in hits][:3]
                chunks: List[str] = []
                for bid in ids:
                    b = _MEM_GET(bid)
                    if not b:
                        continue
                    title = str(b.get("title") or "").strip()
                    content = str(b.get("content") or "").strip().replace("\n", " ")
                    if not content:
                        continue
                    chunks.append(f"• {title}: {content[:220].strip()}")
                    if len(chunks) >= 3:
                        break
                if chunks:
                    mem_note = "\n\n[Relevante Notizen]\n" + "\n".join(chunks)
        except Exception:
            mem_note = ""
        content = (user or "").strip() + (mem_note or "")
        for chunk in llm_local.chat_stream(content, system=(system or "")):
            if chunk:
                yield chunk
        return

    # Fallback: non-streaming and chunk text
    text = respond_to(user, system=system, lang=lang, persona=persona)
    import re
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", text) if p.strip()] or [text]
    for p in parts:
        yield p + " "
