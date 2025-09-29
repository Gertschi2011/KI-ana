import json, re
from pathlib import Path
STOP = set("und oder der die das ein eine einen einem einer ist sind war waren wie was wer wo wann warum wieso weshalb aus mit für auf im in am zum zur von".split())

def get_keywords(text, top=15):
    words = re.findall(r"[a-zA-ZäöüÄÖÜß]{4,}", text.lower())
    freq = {}
    for w in words:
        if w in STOP: continue
        freq[w] = freq.get(w,0)+1
    return sorted(freq, key=freq.get, reverse=True)[:top]

def run(ctx):
    files = ctx["apis"]["read_memory"]()
    texts = []
    for f in files[-20:]:
        try:
            d = json.loads(Path(f).read_text(encoding="utf-8"))
            txt = (d.get("topic","")+" ") + (d.get("content",""))
            texts.append(txt)
        except: pass
    big = " ".join(texts)
    kws = get_keywords(big, 20)
    out = ctx["apis"]["write_memory"]("schlagwort-index", " | ".join(kws))
    return {"keywords": kws, "written_to": out}
