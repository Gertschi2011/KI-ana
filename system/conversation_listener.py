import os
import re
import json
import subprocess
from datetime import datetime
from pathlib import Path
from privacy_enforcer import redact_text
from provenance_append import append_event
# HINWEIS: exec_policy_guard/rate_limit_guard werden hier nicht gebraucht; im Crawler schon.
# from exec_policy_guard import check_network_domain, check_resource_limits
# from rate_limit_guard import allow as ratelimit_allow
# from urllib.parse import urlparse
from personality_engine import style_text, respond_unknown, respond_learned

# ====== Pfade / Dateien ======
BASE_DIR = os.path.expanduser("~/ki_ana/memory")
LONG_TERM_DIR = os.path.join(BASE_DIR, "long_term")
TO_LEARN_FILE = os.path.join(BASE_DIR, "to_learn.txt")
KNOWN_TOPICS_FILE = os.path.join(BASE_DIR, "known_topics.txt")
OPEN_QUESTIONS_FILE = os.path.join(BASE_DIR, "open_questions.json")
TOPIC_INDEX_FILE = os.path.join(BASE_DIR, "topic_index.json")
WEB_CRAWLER = os.path.expanduser("~/ki_ana/system/web_crawler.py")

# ====== Bootstrap ======
os.makedirs(BASE_DIR, exist_ok=True)
os.makedirs(LONG_TERM_DIR, exist_ok=True)
open(TO_LEARN_FILE, "a").close()
open(KNOWN_TOPICS_FILE, "a").close()
if not os.path.exists(OPEN_QUESTIONS_FILE):
    with open(OPEN_QUESTIONS_FILE, "w", encoding="utf-8") as f:
        json.dump({}, f)
if not os.path.exists(TOPIC_INDEX_FILE):
    with open(TOPIC_INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump([], f)

# ====== Heuristik-Listen ======
QUESTION_PREFIXES = [
    "was ist", "was weißt du", "was weisst du", "was weißt du über",
    "was weisst du über", "wer ist", "wer war",
    "warum", "wieso", "weshalb",
    "wie ist", "wie funktioniert", "wie macht man", "wie",
    "wo ist", "woher", "wohin", "wo",
    "wann ist", "wann war", "wann",
    "kennst du", "erklär mir", "erklaer mir"
]
ARTIKEL = {"ein", "eine", "einen", "einem", "einer", "der", "die", "das", "den", "dem", "des"}

# ====== Mini-NLP ======
def preprocess(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()

def is_question(text: str) -> bool:
    t = preprocess(text.lower().replace("ki_ana", ""))
    if "?" in t or t.endswith("?"):
        return True
    if any(t.startswith(p) for p in QUESTION_PREFIXES):
        return True
    if re.match(r"^(bist|hast|kannst|willst|sollst|darfst)\s+du\b", t):
        return True
    return False

def detect_intent(text: str) -> str:
    t = preprocess(text.lower())
    if extract_url(text):
        return "teach_link"
    if is_question(text):
        return "ask"
    if any(t.startswith(cmd) for cmd in ["lern ", "lerne ", "merke ", "crawl ", "suche "]):
        return "command"
    if len(t.split()) > 5 and not is_question(t):
        return "teach_explanation"
    return "talk"

def normalize_topic(text: str) -> str:
    t = preprocess(text.lower().replace("ki_ana", ""))
    for kw in QUESTION_PREFIXES + ["weißt du etwas über", "weißt du ueber"]:
        if kw in t:
            t = t.split(kw, 1)[-1]
            break
    t = t.strip(" ?!.,:;")
    parts = [p for p in t.split() if p]
    while parts and parts[0] in ARTIKEL:
        parts = parts[1:]
    topic = " ".join(parts).strip()
    return topic

def extract_url(text: str):
    m = re.search(r'(https?://\S+)', text)
    return m.group(1) if m else None

def summarize_text(text: str, max_sentences: int = 3, max_chars: int = 700) -> str:
    parts = re.split(r'(?<=[.!?])\s+', preprocess(text))
    summary = " ".join(parts[:max_sentences]).strip()
    if len(summary) > max_chars:
        summary = summary[:max_chars].rsplit(" ", 1)[0] + " ..."
    return summary

COMMAND_PREFIXES = ("python3 ", "sudo ", "apt ", "pip ", "./", "bash ", "sh ", "systemctl ", "crontab ")

def looks_like_shell_command(text: str) -> bool:
    t = text.strip().lower()
    return t.startswith(COMMAND_PREFIXES)

def looks_like_question(text: str) -> bool:
    t = text.strip().lower()
    if "?" in t or t.endswith("?"):
        return True
    prefixes = ["was ist", "was weißt du", "wer ist", "warum", "wie", "wo", "wann", "kennst du", "erklär mir", "erklaer mir"]
    t_no_name = t.replace("ki_ana", "").strip()
    return any(t_no_name.startswith(p) for p in prefixes)

def is_valid_knowledge(text: str) -> bool:
    if looks_like_question(text):
        return False
    clean = re.sub(r"\s+", " ", text).strip()
    return len(clean) >= 30

# ====== Memory-Helpers ======
def load_known_topics():
    with open(KNOWN_TOPICS_FILE, "r", encoding="utf-8") as f:
        return [line.strip().lower() for line in f.readlines()]

def save_known_topic(topic):
    topic = topic.strip().lower()
    if not topic:
        return
    known = load_known_topics()
    if topic in known:
        return
    with open(KNOWN_TOPICS_FILE, "a", encoding="utf-8") as f:
        f.write(f"{topic}\n")

def load_open_questions():
    with open(OPEN_QUESTIONS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_open_questions(data):
    with open(OPEN_QUESTIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def load_topic_index():
    with open(TOPIC_INDEX_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_topic_index(index):
    with open(TOPIC_INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)

def index_add(topic: str, path: str, source: str, timestamp: str):
    topic = topic.lower().strip()
    index = load_topic_index()
    index.append({
        "topic": topic,
        "path": path,
        "source": source,
        "timestamp": timestamp
    })
    save_topic_index(index)

def latest_memory_block():
    p = Path(LONG_TERM_DIR)
    files = sorted(p.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)
    if not files:
        return None
    fp = files[0]
    try:
        data = json.loads(fp.read_text(encoding="utf-8"))
        return (str(fp), data)
    except Exception:
        return None

def find_block_for_topic(topic: str):
    topic = topic.lower().strip()
    index = load_topic_index()
    candidates = [e for e in index if (e["topic"] == topic or e["topic"].startswith(topic) or topic in e["topic"])]
    candidates.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
    for entry in candidates:
        try:
            data = json.loads(Path(entry["path"]).read_text(encoding="utf-8"))
            return (entry["path"], data)
        except Exception:
            pass
    p = Path(LONG_TERM_DIR)
    files = sorted(p.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)
    for fp in files:
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
            content = (data.get("content") or "") + " " + (data.get("topic") or "")
            if topic and topic in content.lower():
                return (str(fp), data)
        except Exception:
            continue
    return None

def save_fact_block(topic: str, content: str) -> str:
    timestamp = datetime.utcnow().isoformat() + "Z"
    block = {
        "type": "manual_fact",
        "topic": topic,
        "content": content,
        "timestamp": timestamp,
        "source": "Papa/Erklärung"
    }
    import hashlib
    name = hashlib.sha256(json.dumps({"t": topic, "ts": timestamp}, sort_keys=True).encode()).hexdigest() + ".json"
    out = Path(LONG_TERM_DIR) / name
    out.write_text(json.dumps(block, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(out)

# ====== Antwort-Bausteine ======
def answer_from_memory(topic: str) -> bool:
    candidate = find_block_for_topic(topic)
    if not candidate:
        return False
    path, data = candidate
    content = data.get("content", "")
    if not is_valid_knowledge(content):
        print(style_text(f"Ich habe etwas zu '{topic.capitalize()}' gespeichert, aber es wirkt wie eine Frage oder ist zu kurz."))
        print(style_text("Magst du mir einen Link schicken oder 1–3 Sätze Erklärung geben?"))
        return True
    source = data.get("source", "unbekannt")
    ts = data.get("timestamp", "")
    summary = summarize_text(content)
    print(f"📚 Aus meinem Gedächtnis über '{topic.capitalize()}':")
    print(f"📝 {summary}")
    print(f"🔎 Quelle: {source}")
    if ts:
        print(f"🕒 Gespeichert am: {ts}")
    print("🌿 Und ganz persönlich: Das Thema ist wichtig für unser Ökosystem.")
    return True

def ask_for_info(topic: str):
    # FIX: clean_topic -> topic
    print(respond_unknown(topic))

def learn_from_link(url: str, topic_hint: str | None):
    pending_topic = topic_hint.lower().strip() if topic_hint else None
    if pending_topic:
        print(f"🌍 Ich lerne jetzt zu '{pending_topic}' aus: {url}")
    else:
        print(f"🌍 Ich lerne aus: {url}")
    subprocess.run(["python3", WEB_CRAWLER], input=f"{url}\n", text=True)
    latest = latest_memory_block()
    if latest:
        path, data = latest
        ts = data.get("timestamp", datetime.utcnow().isoformat() + "Z")
        src = data.get("source", url)
        idx_topic = pending_topic or url.split("/")[-1].split("?")[0].replace("_", " ").strip().lower() or "unbekanntes thema"
        index_add(idx_topic, path, src, ts)
        save_known_topic(idx_topic)
        # FIX: robust bestätigen – immer einen String nehmen
        confirm_topic = (pending_topic or idx_topic).capitalize()
        print(respond_learned(confirm_topic))
    else:
        print("⚠️ Ich konnte keinen neuen Wissensblock finden. Hat der Crawler gespeichert?")

# ====== Start ======
prof = load_profile()
who = (prof.get("active_speaker") or "du")
print(f"🧠 KI_ana Gesprächs-Zuhörer aktiviert.\nHallo {who}! Sag mir etwas – oder 'STOPP' zum Beenden.\n")

known = load_known_topics()
open_q = load_open_questions()

while True:
    user_input = input("👨‍👧 Papa sagt: ").strip()
    # Erst: natürliches Lernen (Name, Likes, Geburtstag, Sprecherwechsel, Vergessen)
    taught, taught_msg = teach_from_sentence(user_input)
    if taught:
        print(taught_msg)
        # danach zur nächsten Eingabe (Intent-Logik überspringen)
        continue
    if looks_like_shell_command(user_input):
        print(style_text("Das sieht nach einem Terminal-Befehl aus. Bitte im Terminal ausführen, nicht im Chat. 😊"))
        continue

    if user_input.lower() == "stopp":
        print(style_text("Okay Papa, ich warte auf den nächsten Impuls."))
        break

    intent = detect_intent(user_input)
    url = extract_url(user_input)
    topic = None if url else normalize_topic(user_input)
    topic = topic if topic else ""

    # Intent: teach_link
    if intent == "teach_link" and url:
        pending_topic = next(iter(open_q.keys())) if open_q else None
        learn_from_link(url, pending_topic)
        if pending_topic:
            del open_q[pending_topic]
            save_open_questions(open_q)
        continue

    # Intent: teach_explanation
    if intent == "teach_explanation" and not url:
        if open_q:
            pending_topic = next(iter(open_q.keys()))
            if not is_valid_knowledge(user_input):
                print(style_text("Deine Erklärung ist noch zu kurz oder klingt wie eine Frage. 1–3 Sätze, keine Frage – dann speichere ich es."))
                continue
            print(f"🔎 Soll ich das als Erklärung zu '{pending_topic.capitalize()}' speichern? (ja/nein)")
            ans = input("> ").strip().lower()
            if ans.startswith("j"):
                explain_text = redact_text(user_input, source_domain="")
                path = save_fact_block(pending_topic, explain_text)
                ts = datetime.utcnow().isoformat() + "Z"
                index_add(pending_topic, path, "Papa/Erklärung", ts)
                save_known_topic(pending_topic)
                append_event({ "type": "manual_fact", "topic": pending_topic, "memory_path": path })
                del open_q[pending_topic]
                save_open_questions(open_q)
                print(respond_learned(pending_topic.capitalize()))
            else:
                print(style_text("Alles klar, ich warte auf einen Link oder eine eindeutige Erklärung."))
        else:
            if topic:
                with open(TO_LEARN_FILE, "a", encoding="utf-8") as f:
                    f.write(topic + "\n")
                print(style_text(f"Ich habe mir gemerkt, dass ich mehr über '{topic}' lernen möchte."))
        continue

    # Intent: ask
    if intent == "ask":
        if topic:
            if answer_from_memory(topic):
                continue
            if topic not in open_q:
                ask_for_info(topic)
                open_q[topic] = "awaiting_answer"
                save_open_questions(open_q)
            else:
                print(style_text(f"Wir warten noch auf eine Erklärung/Link zu '{topic}'."))
        else:
            print(style_text("Ich habe das Thema nicht erkannt. Magst du es nochmal sagen?"))
        continue

    # Intent: command
    if intent == "command":
        print(style_text("Danke! Befehle kann ich bald noch besser verstehen. Fürs Lernen brauche ich Frage + Link oder Erklärung."))
        continue

    # talk / fallback
    if topic and topic not in open_q and topic not in known and not is_question(user_input):
        print(style_text(f"Ich notiere mir '{topic}' auf meine To-Learn-Liste."))
        with open(TO_LEARN_FILE, "a", encoding="utf-8") as f:
            f.write(topic + "\n")
    else:
        print(style_text("Verstanden. Frag mich gern etwas oder gib mir einen Link/Erklärung!"))
