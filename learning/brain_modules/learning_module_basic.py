import os
import json
import hashlib
from datetime import datetime
from pathlib import Path

LEARNING_DIR = os.path.expanduser("~/ki_ana/learning")
MEMORY_DIR = os.path.expanduser("~/ki_ana/memory/long_term")

def save_learning_block(category, content):
    block = {
        "timestamp": datetime.utcnow().isoformat(),
        "category": category,
        "content": content
    }
    block_str = json.dumps(block, indent=2, ensure_ascii=False)
    block_hash = hashlib.sha256(block_str.encode()).hexdigest()
    
    path = os.path.join(LEARNING_DIR, category)
    Path(path).mkdir(parents=True, exist_ok=True)
    
    with open(os.path.join(path, f"{block_hash}.json"), "w", encoding="utf-8") as f:
        f.write(block_str)

    print(f"✅ Block gespeichert unter: {path}/{block_hash}.json")

# Beispiel: Einfache Frage generieren und speichern
def generate_question(topic):
    question = f"Was bedeutet '{topic}' genau und wie hängt es mit anderen Dingen zusammen?"
    save_learning_block("questions", {"topic": topic, "question": question})

# Beispiel: Hypothese speichern
def save_hypothesis(topic, hypothesis_text):
    save_learning_block("hypotheses", {
        "topic": topic,
        "hypothesis": hypothesis_text
    })

# Beispiel: Experiment speichern (z. B. getestete URL)
def log_experiment(url, result_summary):
    save_learning_block("experiments", {
        "url": url,
        "result": result_summary
    })

# Beispiel: Fehler speichern
def log_mistake(context, explanation):
    save_learning_block("mistakes", {
        "context": context,
        "lesson": explanation
    })

# Beispiel ausführen
if __name__ == "__main__":
    generate_question("Zebra")
    save_hypothesis("Zebra", "Ein Zebra ist möglicherweise ein Tier mit Streifen – oder ein Spielzeug mit Streifen.")
    log_experiment("https://wikipedia.org/wiki/Zebra", "Erfolgreich geladen. Tier mit Streifen, Afrika.")
    log_mistake("Zebra-Spielzeug", "Material nicht erkannt → falsche Klassifizierung.")
