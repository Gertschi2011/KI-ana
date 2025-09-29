from __future__ import annotations
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Global limiter instance
limiter = Limiter(key_func=get_remote_address, default_limits=["1000 per hour"])  # coarse default

# Per-route usage example (inside blueprints):
# from backend.core.rate_limit import limiter
# @limiter.limit("100/5minutes")
# def route(): ...
