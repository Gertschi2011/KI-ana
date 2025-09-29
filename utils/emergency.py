import os

EMERGENCY_SHA256 = os.getenv("EMERGENCY_SHA256")  # known SHA256 for Block 1
EMERGENCY_LOCK_PATH = os.getenv("EMERGENCY_LOCK_PATH", "./emergency.lock")


def is_emergency_enabled() -> bool:
    if not EMERGENCY_SHA256:
        return False
    if not os.path.exists(EMERGENCY_LOCK_PATH):
        return False
    try:
        with open(EMERGENCY_LOCK_PATH, "r") as f:
            content = f.read().strip()
        return content == EMERGENCY_SHA256
    except Exception:
        return False
