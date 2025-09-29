from typing import Any, Tuple, List, Optional

def unpack_think(result: Any) -> Tuple[str, List, Optional[dict]]:
    default_blocks, default_web = [], None
    if isinstance(result, str): return result, default_blocks, default_web
    if isinstance(result, dict):
        ans = result.get("answer") or result.get("text") or result.get("reply") or ""
        blocks = result.get("used_blocks") or result.get("memory_blocks") or result.get("blocks") or default_blocks
        web = result.get("web_source") or result.get("web") or result.get("source") or default_web
        return ans, blocks, web
    if isinstance(result, (tuple, list)):
        if not result: return "", default_blocks, default_web
        if len(result) == 1: return result[0] or "", default_blocks, default_web
        if len(result) == 2: return result[0] or "", result[1] or default_blocks, default_web
        return result[0] or "", result[1] or default_blocks, result[2] or default_web
    return str(result or ""), default_blocks, default_web
