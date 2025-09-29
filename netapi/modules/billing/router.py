from __future__ import annotations
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from pathlib import Path
import io, tarfile, time, secrets, hashlib, json, shutil

from ...deps import get_db, get_current_user_required
from ...db import SessionLocal
from ...models import User

router = APIRouter(prefix="/api", tags=["billing"])

KI_ROOT = Path.home() / "ki_ana"
RUNTIME = KI_ROOT / "system" / "submind_runtime"
SUBM_DIR = KI_ROOT / "subminds"
SUBM_DIST = SUBM_DIR / "dist"
SUBM_DIR.mkdir(parents=True, exist_ok=True)
SUBM_DIST.mkdir(parents=True, exist_ok=True)
OS_DIST = KI_ROOT / "os" / "dist"
OS_DIST.mkdir(parents=True, exist_ok=True)


# ---- Plans -----------------------------------------------------------------
class Plan(BaseModel):
    id: str
    name: str
    period: str  # monthly|yearly|oneoff
    price_eur: float
    includes_submind: bool = True


PLANS: List[Plan] = [
    Plan(id="submind_monthly", name="Submind Abo (Monat)", period="monthly", price_eur=4.99),
    Plan(id="submind_yearly", name="Submind Abo (Jahr)", period="yearly", price_eur=49.0),
]


@router.get("/plans")
def list_plans() -> Dict[str, Any]:
    return {"items": [p.model_dump() for p in PLANS]}


# ---- Paylink (Web placeholder) --------------------------------------------
@router.get("/paylink")
def paylink(plan: str, user = Depends(get_current_user_required)):
    # In echter Umgebung hier Stripe/Provider Link generieren.
    # Für MVP: wenn Nutzer bereits aktiv, biete direkten Download an.
    now = int(time.time())
    until = int(user.get("plan_until") or 0)
    if (user.get("plan") or "").startswith("submind_") and until > now:
        return {"ok": True, "url": "/api/subminds/package"}
    # Placeholder: leitet auf Pricing zurück
    return {"ok": True, "url": "/pricing"}


# ---- Subscription confirm (receipt stub) ----------------------------------
class ConfirmIn(BaseModel):
    platform: str = Field(pattern="^(ios|android|web)$")
    plan: str
    receipt: str  # app store receipt / token / web session id


@router.post("/subscription/confirm")
def subscription_confirm(body: ConfirmIn, db = Depends(get_db), user = Depends(get_current_user_required)):
    # Stub: akzeptiert TEST/DEV Receipts. Setzt plan + plan_until entsprechend.
    r = (body.receipt or "").strip().upper()
    if not (r.startswith("TEST") or r.startswith("DEV") or r.startswith("WEB")):
        raise HTTPException(400, "invalid_receipt")
    months = 1 if body.plan.endswith("monthly") else 12
    now = int(time.time())
    until = now + months * 30 * 24 * 3600
    # Update user
    u: User = db.query(User).filter(User.id == int(user["id"])).first()  # type: ignore
    if not u:
        raise HTTPException(404, "user_not_found")
    u.plan = body.plan
    u.plan_until = until
    u.updated_at = int(time.time())
    db.commit()
    return {"ok": True, "plan": body.plan, "plan_until": until}


# ---- Package download (generates user-specific submind bundle) -------------
def _ensure_submind_registered(user_id: int) -> Dict[str, Any]:
    sid = f"baby-{user_id}"
    d = SUBM_DIR / sid
    cfgp = d / "config.json"
    if d.exists() and cfgp.exists():
        try:
            return json.loads(cfgp.read_text(encoding="utf-8"))
        except Exception:
            pass
    d.mkdir(parents=True, exist_ok=True)
    api_key = secrets.token_urlsafe(32)
    api_hash = hashlib.sha256(api_key.encode("utf-8")).hexdigest()
    cfg = {
        "submind_id": sid,
        "role": "child",
        "description": "Persönliche Submind‑App",
        "parent_endpoint": "/api",
        "api_key_hash": api_hash,
        "created_at": int(time.time()),
    }
    cfgp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    # speichere Key im Klartext für Packager/Nutzer
    (d / "api.key").write_text(api_key, encoding="utf-8")
    return cfg


def _build_package(user_id: int, username: str, server_base: str) -> Path:
    sid = f"baby-{user_id}"
    cfg = _ensure_submind_registered(user_id)
    # Arbeitsverzeichnis kopieren
    work = SUBM_DIST / f"{sid}_build"
    if work.exists():
        shutil.rmtree(work)
    shutil.copytree(RUNTIME, work)
    # config.json schreiben
    config = {
        "submind_id": sid,
        "license_key": f"LIC-{user_id}-{int(time.time())}",
        "parent_endpoint": server_base.rstrip('/') + "/api",
        "parent_pubkey": "",
        "policies": {"allow_domains": ["de.wikipedia.org","wikipedia.org","britannica.com"], "timeout_sec": 15},
    }
    (work / "config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    # api.key beilegen
    api_key_file = SUBM_DIR / sid / "api.key"
    if api_key_file.exists():
        shutil.copy2(api_key_file, work / "api.key")
    # Hilfsskripte beilegen: Submind-Client (zum Senden der Outbox)
    try:
        client_src = KI_ROOT / "system" / "submind_client.py"
        if client_src.exists():
            shutil.copy2(client_src, work / "send_client.py")
    except Exception:
        pass

    # README beilegen
    (work / "README.txt").write_text(
        "Submind Paket\n"
        f"User: {username} (ID {user_id})\n"
        f"ID: {sid}\n"
        "Installation: ./install_submind.sh [Zielpfad]\n"
        "Start (Interaktiv): python3 runtime_listener.py\n"
        "Senden (Outbox/Mem): python3 send_client.py --id {sid} --base {server}\n".replace("{sid}", sid).replace("{server}", server_base),
        encoding="utf-8"
    )
    # Archiv erstellen
    tarpath = SUBM_DIST / f"submind_{sid}.tar.gz"
    if tarpath.exists():
        tarpath.unlink()
    with tarfile.open(tarpath, "w:gz") as tar:
        tar.add(work, arcname=f"submind_{sid}")
    shutil.rmtree(work, ignore_errors=True)
    return tarpath


@router.get("/subminds/package")
def download_package(request: Request, user = Depends(get_current_user_required), db = Depends(get_db)):
    # Prüfe Abo
    u: User = db.query(User).filter(User.id == int(user["id"])).first()  # type: ignore
    if not u:
        raise HTTPException(404, "user_not_found")
    now = int(time.time())
    if not (u.plan or "").startswith("submind_") or int(u.plan_until or 0) <= now:
        raise HTTPException(402, "subscription_required")
    scheme = request.url.scheme
    host = request.headers.get("host") or "localhost"
    server_base = f"{scheme}://{host}"
    tarpath = _build_package(u.id, u.username, server_base)
    return FileResponse(tarpath, media_type="application/gzip", filename=tarpath.name)


# ---- OS installer package (KI_ana OS) -------------------------------------
def _build_os_package(user_id: int, username: str, server_base: str) -> Path:
    src = KI_ROOT / "system" / "os_installer"
    if not src.exists():
        raise HTTPException(500, "os_installer missing")
    work = OS_DIST / f"os_{user_id}_build"
    if work.exists():
        shutil.rmtree(work)
    shutil.copytree(src, work)
    # user config
    cfg = {"user_id": user_id, "username": username, "created_at": int(time.time()), "server_base": server_base}
    (work / "config.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    tarpath = OS_DIST / f"kiana_os_{user_id}.tar.gz"
    if tarpath.exists():
        tarpath.unlink()
    with tarfile.open(tarpath, "w:gz") as tar:
        tar.add(work, arcname="kiana_os")
    shutil.rmtree(work, ignore_errors=True)
    return tarpath


@router.get("/os/package")
def download_os_package(request: Request, user = Depends(get_current_user_required), db = Depends(get_db)):
    # Abo prüfen (nutzt dieselben submind_* Pläne)
    u: User = db.query(User).filter(User.id == int(user["id"])).first()  # type: ignore
    if not u:
        raise HTTPException(404, "user_not_found")
    now = int(time.time())
    if not (u.plan or "").startswith("submind_") or int(u.plan_until or 0) <= now:
        raise HTTPException(402, "subscription_required")
    scheme = request.url.scheme
    host = request.headers.get("host") or "localhost"
    server_base = f"{scheme}://{host}"
    tarpath = _build_os_package(u.id, u.username, server_base)
    return FileResponse(tarpath, media_type="application/gzip", filename=tarpath.name)
