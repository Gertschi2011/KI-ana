from typing import List, Optional
try:
    from ... import memory_store as _mem
except Exception:
    _mem = None

def save_note(title: str, content: str, tags: List[str], url: Optional[str] = None):
    if not _mem or not hasattr(_mem, "add_block"):
        return
    try:
        _mem.add_block(title=title[:200], content=content, tags=tags, url=url, meta={"source":"chat"})
    except Exception:
        pass