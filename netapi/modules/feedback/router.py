from __future__ import annotations
from fastapi import APIRouter, Body, HTTPException, Depends
from fastapi.responses import JSONResponse
from typing import Optional, Dict, Any
from pathlib import Path
from importlib.machinery import SourceFileLoader
from netapi.deps import get_current_user_required
import time, json

router = APIRouter(prefix="/feedback", tags=["feedback"])
BASE_DIR = Path(os.getenv("KI_ROOT", str(Path.home() / "ki_ana")))
BLOCKS_DIR = BASE_DIR / "memory" / "long_term" / "blocks"


def _sign(block: Dict[str, Any]) -> Dict[str, Any]:
    mod = SourceFileLoader("block_signer", str(BASE_DIR / "system" / "block_signer.py")).load_module()  # type: ignore
    sig, pub, ts = mod.sign_block(block)  # type: ignore
    block["signature"], block["pubkey"], block["signed_at"] = sig, pub, ts
    return block


@router.post("")
async def post_feedback(
    response_id: str = Body(..., embed=True),
    helpfulness: Optional[float] = Body(None, embed=True),
    clarity: Optional[float] = Body(None, embed=True),
    comment: Optional[str] = Body(None, embed=True),
    user = Depends(get_current_user_required),
):
    try:
        BLOCKS_DIR.mkdir(parents=True, exist_ok=True)
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        fb = {
            "id": f"feedback_{int(time.time())}",
            "title": "User Feedback",
            "topic": "meta/feedback",
            "content": comment or "",
            "source": "user",
            "timestamp": now,
            "tags": ["feedback", "meta"],
            "meta": {
                "provenance": "feedback",
                "response_id": response_id,
                "helpfulness": helpfulness,
                "clarity": clarity,
                "user": user.get("username"),
            },
        }
        fb = _sign(fb)
        path = BLOCKS_DIR / f"{fb['id']}.json"
        path.write_text(json.dumps(fb, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        return JSONResponse({"ok": True, "id": fb["id"], "path": str(path)})
    except Exception as e:
        raise HTTPException(500, f"feedback failed: {e}")
