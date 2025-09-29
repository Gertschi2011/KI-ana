import os

BASE_DIR = os.path.expanduser("~/ki_ana/memory")
TO_LEARN_FILE = os.path.join(BASE_DIR, "to_learn.txt")
KNOWN_TOPICS_FILE = os.path.join(BASE_DIR, "known_topics.txt")

# Sicherstellen, dass Dateien existieren
os.makedirs(BASE_DIR, exist_ok=True)
open(TO_LEARN_FILE, "a").close()
open(KNOWN_TOPICS_FILE, "a").close()

def load_known_topics():
    with open(KNOWN_TOPICS_FILE, "r", encoding="utf-8") as f:
        return [line.strip().lower() for line in f.readlines()]

def save_to_learn(topic):
    with open(TO_LEARN_FILE, "a", encoding="utf-8") as f:
        f.write(f"{topic}\n")

def extract_topic_from_input(text):
    text = text.lower()
    if "ki_ana" in text:
        text = text.replace("ki_ana", "").strip()

        # Erkennung gängiger Frageformen
        for prefix in ["kennst du", "was ist", "weißt du etwas über", "erklär mir", "was weißt du über", "wer ist", "wie ist" "wo ist" "warum ist", "warum soll"]:
            if prefix in text:
                return text.split(prefix)[-1].strip().capitalize()

    return text.strip().capitalize()

def topic_in_known_list(topic):
    return topic.lower() in load_known_topics()

# 🧠 Gespräch starten
print("🧠 KI_ana Gesprächs-Zuhörer aktiviert.")
print("Sag mir bitte, was ich mir merken soll – oder schreibe 'STOPP' zum Beenden.\n")

while True:
    raw_input_text = input("👨‍👧 Papa sagt: ")

    if raw_input_text.strip().lower() == "stopp":
        print("👋 Okay Papa, ich merke mir das und warte auf den nächsten Impuls.")
        break

    topic = extract_topic_from_input(raw_input_text)

    if not topic:
        print("❓ Ich habe leider nicht verstanden, worum es geht.")
        continue

    if topic_in_known_list(topic):
        print(f"😊 Ja Papa, über '{topic}' habe ich schon etwas gelernt!")
    else:
        print(f"🧐 Papa, ich weiß noch nichts über '{topic}'. Kannst du es mir erklären oder eine Webseite zeigen?")
        print(f"📌 Ich habe mir gemerkt, dass ich mehr über '{topic}' lernen möchte!")
        save_to_learn(topic)
