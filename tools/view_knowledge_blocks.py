import os
import json
from datetime import datetime

MEMORY_DIR = os.path.expanduser("~/ki_ana/memory/long_term")

def load_blocks():
    blocks = []
    for filename in os.listdir(MEMORY_DIR):
        if filename.endswith(".json"):
            filepath = os.path.join(MEMORY_DIR, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    blocks.append(data)
            except Exception as e:
                print(f"❌ Fehler beim Laden {filename}: {e}")
    return blocks

def search_blocks(blocks, keyword):
    results = []
    for block in blocks:
        if "content" in block and keyword.lower() in block["content"].lower():
            results.append(block)
    return results

def group_by_source(results):
    grouped = {}
    for block in results:
        source = block.get("source", "🗂️ Unbekannte Quelle")
        grouped.setdefault(source, []).append(block)
    return grouped

def display_results(grouped):
    for source, blocks in grouped.items():
        print("\n🌐 Quelle:", source)
        print("📦 Treffer:", len(blocks))
        for block in blocks:
            ts = block.get("timestamp", "Unbekannt")
            date_str = datetime.fromisoformat(ts).strftime("%d.%m.%Y %H:%M:%S") if "T" in ts else ts
            snippet = block['content'][:200].replace('\n', ' ')
            print(f"  └ 🕒 {date_str}")
            print(f"     🔹 {snippet}...")

def main():
    print("🧠 KI_ana Wissen-Viewer v2")
    keyword = input("🔍 Nach welchem Schlagwort willst du suchen? ").strip()
    if not keyword:
        print("⛔ Kein Suchbegriff eingegeben.")
        return

    print("🔄 Lade Blöcke...")
    blocks = load_blocks()
    print(f"📚 {len(blocks)} Blöcke geladen.")

    print(f"🔎 Suche nach '{keyword}'...")
    results = search_blocks(blocks, keyword)
    print(f"✅ {len(results)} Treffer gefunden.")

    if results:
        grouped = group_by_source(results)
        display_results(grouped)

if __name__ == "__main__":
    main()
