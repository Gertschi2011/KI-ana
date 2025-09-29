import os
import subprocess
import urllib.parse
import time

TO_LEARN_PATH = os.path.expanduser("~/ki_ana/learning/to_learn.txt")
DUCKDUCKGO_BASE = "https://duckduckgo.com/?q="

def read_learning_goals():
    if not os.path.exists(TO_LEARN_PATH):
        return []
    with open(TO_LEARN_PATH, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]
    return lines

def generate_url(topic):
    encoded = urllib.parse.quote(topic)
    return f"https://en.wikipedia.org/wiki/{encoded}"

def crawl_topic(url):
    print(f"🌍 Lerne über: {url}")
    subprocess.run(["python3", os.path.expanduser("~/ki_ana/system/web_crawler.py")], input=f"{url}\n", text=True)

def manual_reflection():
    subprocess.run(["python3", os.path.expanduser("~/ki_ana/system/manual_learn.py")])

def remove_learned_topic(topic):
    with open(TO_LEARN_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()
    with open(TO_LEARN_PATH, "w", encoding="utf-8") as f:
        for line in lines:
            if line.strip() != topic:
                f.write(line)

def main():
    print("🧠 KI_ana Selbstbewusstseins-Routine startet...")

    topics = read_learning_goals()
    if not topics:
        print("📭 Keine Lernziele gefunden.")
        return

    for topic in topics:
        print(f"\n🔎 Ziel: {topic}")
        url = generate_url(topic)

        crawl_topic(url)
        time.sleep(2)  # kurz warten, falls z. B. Crawler noch nicht abgeschlossen
        manual_reflection()

        remove_learned_topic(topic)
        print(f"✅ Gelernt & reflektiert: {topic}")

    print("\n✨ Selbstlernroutine abgeschlossen.")

if __name__ == "__main__":
    main()
