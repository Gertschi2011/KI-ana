from __future__ import annotations
import io
import os
import json
import zipfile
from pathlib import Path
from typing import List

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/api/export", tags=["export"])

BASE_DIR = Path(os.getenv("KI_ROOT", str(Path.home() / "ki_ana")))
BLOCKS_DIR = BASE_DIR / "memory" / "long_term" / "blocks"
SUBKI_TRUST = BASE_DIR / "memory" / "subki" / "trust.json"
INDEX_MAIN = BASE_DIR / "memory" / "index" / "index.json"
INDEX_CRAWLED = BASE_DIR / "memory" / "index" / "crawled_index.json"


def _add_file(zf: zipfile.ZipFile, disk_path: Path, arcname: str) -> None:
    try:
        if disk_path.exists():
            zf.write(str(disk_path), arcname)
    except Exception:
        # Skip unreadable files but keep archive creation robust
        pass


@router.get("/blocks")
def export_blocks():
    """Package blocks/*.json + subki/trust.json + index files into a ZIP and stream it."""
    try:
        mem = io.BytesIO()
        with zipfile.ZipFile(mem, mode="w", compression=zipfile.ZIP_DEFLATED) as z:
            # Blocks
            if BLOCKS_DIR.exists():
                for p in sorted(BLOCKS_DIR.glob("*.json")):
                    _add_file(z, p, f"blocks/{p.name}")
            # Trust map
            _add_file(z, SUBKI_TRUST, "subki/trust.json")
            # Indices
            _add_file(z, INDEX_MAIN, "index/index.json")
            _add_file(z, INDEX_CRAWLED, "index/crawled_index.json")
        mem.seek(0)
        headers = {
            "Content-Disposition": "attachment; filename=ki_ana_export.zip"
        }
        return StreamingResponse(mem, media_type="application/zip", headers=headers)
    except Exception as e:
        raise HTTPException(500, f"export_error: {e}")
