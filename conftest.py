import os
import sys
from pathlib import Path

# Ensure repository root on sys.path so imports like 'ki_ana.netapi' work
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Sensible defaults for tests
os.environ.setdefault("DATABASE_URL", "sqlite:///test.db")
os.environ.setdefault("LOG_LEVEL", "WARNING")
os.environ.setdefault("TEST_MODE", "1")

# Many routers (including /api/chat) are mounted with require_active_user at the app level.
# For unit tests we override this dependency to avoid hard auth requirements.
try:
    from netapi.app import app
    from netapi.deps import require_active_user
    try:
        from fastapi import Request
    except Exception:
        Request = object  # type: ignore

    def _test_active_user(request: Request = None, current=None, db=None):  # type: ignore[valid-type]
        return {
            "id": 1,
            "username": "test",
            "role": "creator",
            "roles": ["creator"],
            "is_admin": True,
            "email_verified": True,
            "account_status": "active",
            "subscription_status": "active",
            "consent_learning": "ask",
        }

    app.dependency_overrides[require_active_user] = _test_active_user
except Exception:
    pass
