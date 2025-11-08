"""
Audit API Router
Provides endpoints for knowledge quality audits
Sprint 6.2 - Metakognition
"""
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import JSONResponse
from pathlib import Path
from pydantic import BaseModel
import json
import subprocess
import time
from typing import Optional


router = APIRouter(prefix="/api/audit", tags=["audit"])

AUDIT_DIR = Path("/home/kiana/ki_ana/data/audit")
AUDIT_TOOL = Path("/home/kiana/ki_ana/tools/knowledge_audit.py")


class AuditConfig(BaseModel):
    """Configuration for audit run"""
    max_age_days: int = 180
    min_trust: float = 5.0


# Track running audits
_audit_status = {
    "running": False,
    "last_run": 0,
    "last_duration_ms": 0,
    "last_error": None
}


def _run_audit_background(max_age_days: int, min_trust: float):
    """Run audit in background"""
    global _audit_status
    
    try:
        _audit_status["running"] = True
        _audit_status["last_error"] = None
        start_time = time.time()
        
        # Run audit tool
        result = subprocess.run(
            [
                "python3",
                str(AUDIT_TOOL),
                "--max-age-days", str(max_age_days),
                "--min-trust", str(min_trust)
            ],
            capture_output=True,
            text=True,
            timeout=300  # 5 minutes max
        )
        
        if result.returncode != 0:
            _audit_status["last_error"] = result.stderr
        else:
            _audit_status["last_run"] = int(time.time())
            _audit_status["last_duration_ms"] = int((time.time() - start_time) * 1000)
            
    except subprocess.TimeoutExpired:
        _audit_status["last_error"] = "Audit timed out after 5 minutes"
    except Exception as e:
        _audit_status["last_error"] = str(e)
    finally:
        _audit_status["running"] = False


@router.post("/run")
async def run_audit(
    config: AuditConfig,
    background_tasks: BackgroundTasks
):
    """
    Trigger knowledge audit
    
    Runs in background and generates:
    - Audit report (JSON)
    - Audit block (type: self_audit)
    - Recommendations
    """
    if _audit_status["running"]:
        return JSONResponse(
            {"ok": False, "error": "Audit already running"},
            status_code=409
        )
    
    # Start audit in background
    background_tasks.add_task(
        _run_audit_background,
        config.max_age_days,
        config.min_trust
    )
    
    return JSONResponse({
        "ok": True,
        "message": "Audit started",
        "config": {
            "max_age_days": config.max_age_days,
            "min_trust": config.min_trust
        }
    })


@router.get("/status")
async def get_audit_status():
    """
    Get current audit status
    
    Returns whether an audit is running and when last completed.
    """
    return JSONResponse({
        "ok": True,
        "status": {
            "running": _audit_status["running"],
            "last_run": _audit_status["last_run"],
            "last_run_human": (
                None if not _audit_status["last_run"]
                else time.strftime(
                    "%Y-%m-%d %H:%M:%S",
                    time.localtime(_audit_status["last_run"])
                )
            ),
            "last_duration_ms": _audit_status["last_duration_ms"],
            "last_error": _audit_status["last_error"]
        }
    })


@router.get("/latest")
async def get_latest_report():
    """
    Get latest audit report
    
    Returns the most recent audit results.
    """
    latest_file = AUDIT_DIR / "latest_audit.json"
    
    if not latest_file.exists():
        return JSONResponse({
            "ok": False,
            "error": "No audit reports found. Run an audit first."
        }, status_code=404)
    
    try:
        with open(latest_file, 'r', encoding='utf-8') as f:
            report = json.load(f)
        
        return JSONResponse({
            "ok": True,
            "report": report
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
async def get_audit_history(
    limit: int = Query(10, ge=1, le=50, description="Number of reports to return")
):
    """
    Get audit history
    
    Returns list of past audit reports.
    """
    if not AUDIT_DIR.exists():
        return JSONResponse({"ok": True, "reports": []})
    
    # Find all audit files
    audit_files = sorted(
        AUDIT_DIR.glob("audit_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )[:limit]
    
    reports = []
    for file in audit_files:
        try:
            with open(file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                reports.append({
                    "filename": file.name,
                    "timestamp": data.get("timestamp"),
                    "stats": data.get("stats", {}),
                    "recommendations_count": len(data.get("recommendations", []))
                })
        except:
            pass
    
    return JSONResponse({
        "ok": True,
        "reports": reports,
        "count": len(reports)
    })


@router.get("/stale")
async def get_stale_blocks(
    limit: int = Query(100, ge=1, le=500, description="Maximum results")
):
    """
    Get list of stale blocks
    
    Returns blocks that need updating.
    """
    latest_file = AUDIT_DIR / "latest_audit.json"
    
    if not latest_file.exists():
        return JSONResponse({
            "ok": False,
            "error": "No audit found. Run audit first."
        }, status_code=404)
    
    with open(latest_file, 'r', encoding='utf-8') as f:
        report = json.load(f)
    
    stale = report.get("stale", {})
    blocks = stale.get("blocks", [])[:limit]
    
    return JSONResponse({
        "ok": True,
        "stale_blocks": blocks,
        "total_count": stale.get("count", 0),
        "returned_count": len(blocks)
    })


@router.get("/conflicts")
async def get_conflict_blocks(
    limit: int = Query(100, ge=1, le=500, description="Maximum results")
):
    """
    Get list of blocks with conflicts
    
    Returns blocks that have contradictions.
    """
    latest_file = AUDIT_DIR / "latest_audit.json"
    
    if not latest_file.exists():
        return JSONResponse({
            "ok": False,
            "error": "No audit found. Run audit first."
        }, status_code=404)
    
    with open(latest_file, 'r', encoding='utf-8') as f:
        report = json.load(f)
    
    conflicts = report.get("conflicts", {})
    blocks = conflicts.get("blocks", [])[:limit]
    
    return JSONResponse({
        "ok": True,
        "conflict_blocks": blocks,
        "total_count": conflicts.get("count", 0),
        "returned_count": len(blocks)
    })
