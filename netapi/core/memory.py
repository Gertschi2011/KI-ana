from pathlib import Path
import json, time

MEMORY_DIR = Path("memory")

def ensure_dirs():
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)

def add_block(title, content, tags=None, url=None):
    ensure_dirs()
    ts = int(time.time())
    block = {
        "title": title,
        "content": content,
        "tags": tags or [],
        "url": url,
        "created_at": ts
    }
    fname = MEMORY_DIR / f"{ts}_{title[:30].replace(' ', '_')}.json"
    with open(fname, "w", encoding="utf-8") as f:
        json.dump(block, f, indent=2)


# Contextual memory search
def search_memory(query: str, top_k: int = 5):
    ensure_dirs()
    results = []
    for file in MEMORY_DIR.glob("*.json"):
        with open(file, "r", encoding="utf-8") as f:
            try:
                block = json.load(f)
                score = 0
                if query.lower() in block.get("title", "").lower():
                    score += 1
                if query.lower() in block.get("content", "").lower():
                    score += 1
                if any(query.lower() in tag.lower() for tag in block.get("tags", [])):
                    score += 0.5
                if score > 0:
                    results.append((score, block))
            except Exception:
                continue
    results.sort(reverse=True, key=lambda x: x[0])
    return [r[1] for r in results[:top_k]]