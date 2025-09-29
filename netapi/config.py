# netapi/config.py
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# Verzeichnisse
NETAPI_DIR     = Path(__file__).resolve().parent          # .../netapi
PROJECT_ROOT   = NETAPI_DIR.parent                        # Projekt-Root
STATIC_DIR     = NETAPI_DIR / "static"
TEMPLATES_DIR  = NETAPI_DIR / "templates"                 # falls du später Jinja/HTML nutzt
DEFAULT_DB     = f"sqlite:///{PROJECT_ROOT / 'db.sqlite3'}"

class Settings(BaseSettings):
    # Feature-Flags & Defaults
    DEBUG: bool = False
    SSE_ENABLED: bool = True
    AUTOPILOT_INTERVAL_MIN: int = 15
    # Networking / deployment
    ROOT_PATH: str = ""
    ALLOW_NET: bool = True

    # Local LLM (Ollama)
    OLLAMA_HOST: str = "http://127.0.0.1:11434"
    OLLAMA_MODEL: str = "llama3.1:8b"

    # Search APIs (optional)
    GOOGLE_CSE_API_KEY: str | None = None
    GOOGLE_CSE_CX: str | None = None
    YOUTUBE_API_KEY: str | None = None

    # Secrets / Infra
    KI_SECRET: str = "dev-secret-change-me"
    DATABASE_URL: str = DEFAULT_DB

    # pydantic-settings v2: .env im Projektroot, Extra ignorieren
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        extra="ignore"
    )

settings = Settings()
