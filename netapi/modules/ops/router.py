from __future__ import annotations

import os
import time
from typing import Any, Dict

from fastapi import APIRouter, Depends

from ...deps import get_current_user_required, require_admin_only

router = APIRouter(prefix="/api/ops", tags=["ops"])


@router.get("/summary")
def ops_summary(user=Depends(get_current_user_required)) -> Dict[str, Any]:
    require_admin_only(user)

    sha = (os.getenv("KIANA_BUILD_SHA") or os.getenv("BUILD_SHA") or "").strip() or None
    env_value = (os.getenv("KIANA_ENV") or os.getenv("ENV") or "dev").strip().lower() or "dev"

    return {
        "ok": True,
        "env": env_value,
        "sha": sha,
        "now_ts": int(time.time()),
    }
