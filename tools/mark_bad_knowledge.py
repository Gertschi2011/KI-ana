import os, json, re
from pathlib import Path

LONG = Path.home() / "ki_ana/memory/long_term"
changed = 0

def looks_like_question(text: str) -> bool:
    t = text.strip().lower()
    if "?" in t or t.endswith("?"): return True
    prefixes = ["was ist", "was weißt du", "wer ist", "warum", "wie", "wo", "wann", "kennst du", "erklär mir", "erklaer mir"]
    t = t.replace("ki_ana", "").strip()
    return any(t.startswith(p) for p in prefixes)

for f in LONG.glob("*.json"):
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
        content = data.get("content", "")
        if looks_like_question(content) or len(re.sub(r"\s+"," ",content).strip()) < 30:
            if data.get("quality") != "low":
                data["quality"] = "low"
                f.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
                changed += 1
    except Exception:
        pass

print(f"Marked {changed} low-quality knowledge blocks.")
