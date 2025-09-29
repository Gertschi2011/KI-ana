from __future__ import annotations
from typing import Optional
import time

from .db import SessionLocal
from .models import User
from netapi.modules.auth.crypto import hash_pw

def seed_users() -> None:
    """Idempotently seed initial users needed for local/dev.
    - Adds user 'gerald' with email 'gerald.stiefsohn@gmx.at' and role 'creator'
      (creator implies papa in the frontend via /api/me role derivation).
    """
    try:
        with SessionLocal() as db:
            # Already present?
            exists = db.query(User).filter(User.username == 'gerald').first()
            if exists:
                return
            u = User(
                username='gerald',
                email='gerald.stiefsohn@gmx.at',
                password_hash=hash_pw('Jawohund2011!'),
                role='creator',
                plan='free',
                plan_until=0,
                created_at=int(time.time()),
                updated_at=int(time.time()),
            )
            db.add(u)
            db.commit()
    except Exception:
        # Never crash app on seed failure
        pass
