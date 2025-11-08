"""OS module - Operating system abstractions and device management."""

from .router import router
from .capabilities import allowed_caps
from . import syscalls

__all__ = ["router", "allowed_caps", "syscalls"]
