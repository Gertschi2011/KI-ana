from fastapi import APIRouter
from fastapi.responses import FileResponse, Response
from pathlib import Path
from ...config import STATIC_DIR

router = APIRouter()

def _s(*parts: str) -> Path:
    return STATIC_DIR.joinpath(*parts)

# Root (Index)
@router.get("/", include_in_schema=False)
def index():
    return FileResponse(_s("index.html"))

# Favicon & Apple Touch
@router.get("/favicon.ico", include_in_schema=False)
def favicon():
    return FileResponse(_s("favicon.ico"))

@router.get("/apple-touch-icon.png", include_in_schema=False)
def apple_touch():
    return FileResponse(_s("apple-touch-icon.png"))

# Einfache statische Seiten
@router.get("/login", include_in_schema=False)
def login():
    return FileResponse(_s("login.html"))

@router.get("/register", include_in_schema=False)
def register():
    return FileResponse(_s("register.html"))

@router.get("/privacy", include_in_schema=False)
def privacy():
    return FileResponse(_s("privacy.html"))

@router.get("/agb", include_in_schema=False)
def agb():
    return FileResponse(_s("agb.html"))

@router.get("/impressum", include_in_schema=False)
def impressum():
    return FileResponse(_s("impressum.html"))

@router.get("/about", include_in_schema=False)
def about():
    return FileResponse(_s("about.html"))

@router.get("/pricing", include_in_schema=False)
def pricing():
    return FileResponse(_s("pricing.html"))

@router.get("/chat", include_in_schema=False)
def chat_page():
    return FileResponse(_s("chat.html"))

# Zusätzliche statische Seiten kurzschließen
@router.get("/capabilities", include_in_schema=False)
def capabilities():
    return FileResponse(_s("capabilities.html"))

@router.get("/logout", include_in_schema=False)
def logout_page():
    return FileResponse(_s("logout.html"))

# Neue/zusätzliche Seiten (aus Static), damit schöne Kurz-URLs funktionieren
@router.get("/downloads", include_in_schema=False)
def downloads():
    return FileResponse(_s("downloads.html"))

@router.get("/skills", include_in_schema=False)
def skills():
    return FileResponse(_s("skills.html"))

@router.get("/search", include_in_schema=False)
def search():
    return FileResponse(_s("search.html"))

@router.get("/cron", include_in_schema=False)
def cron():
    return FileResponse(_s("cron.html"))

@router.get("/kids", include_in_schema=False)
def kids():
    return FileResponse(_s("kids.html"))

@router.get("/papa", include_in_schema=False)
def papa():
    return FileResponse(_s("papa.html"))

@router.get("/guardian", include_in_schema=False)
def guardian():
    return FileResponse(_s("guardian.html"))

# Auth/Account Hilfsseiten
@router.get("/forgot", include_in_schema=False)
def forgot():
    return FileResponse(_s("forgot.html"))

@router.get("/reset", include_in_schema=False)
def reset():
    return FileResponse(_s("reset.html"))

# Payment Flow Seiten
@router.get("/subscribe", include_in_schema=False)
def subscribe():
    return FileResponse(_s("subscribe.html"))

@router.get("/thanks", include_in_schema=False)
def thanks():
    return FileResponse(_s("thanks.html"))

@router.get("/cancel", include_in_schema=False)
def cancel():
    return FileResponse(_s("cancel.html"))

# Falls du nav.html per <iframe> lädst
@router.get("/static/nav.html", include_in_schema=False)
def nav_html():
    return FileResponse(_s("nav.html"))

# Optional kurzer Pfad für Navigation
@router.get("/nav", include_in_schema=False)
def nav_short():
    return FileResponse(_s("nav.html"))

# Fallback-Static (hilft, wenn das StaticFiles-Mount in app.py mal nicht greift)
@router.get("/static/{path:path}", include_in_schema=False)
def static_fallback(path: str):
    p = STATIC_DIR / path
    if p.is_file():
        return FileResponse(p)
    return Response(status_code=404)
