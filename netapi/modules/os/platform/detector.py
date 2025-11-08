"""Cross-platform OS detection and information gathering."""

from __future__ import annotations
import platform
import sys
from typing import Dict, Any, Optional

# Cache the detected platform
_PLATFORM_CACHE: Optional[str] = None
_INFO_CACHE: Optional[Dict[str, Any]] = None


def detect_platform() -> str:
    """
    Detect current operating system platform.
    
    Returns:
        Platform identifier: "linux", "windows", "macos", or "unknown"
    """
    global _PLATFORM_CACHE
    if _PLATFORM_CACHE is not None:
        return _PLATFORM_CACHE
    
    try:
        system = platform.system().lower()
        if system == "linux":
            _PLATFORM_CACHE = "linux"
        elif system == "windows":
            _PLATFORM_CACHE = "windows"
        elif system == "darwin":
            _PLATFORM_CACHE = "macos"
        else:
            _PLATFORM_CACHE = "unknown"
    except Exception:
        _PLATFORM_CACHE = "unknown"
    
    return _PLATFORM_CACHE


def get_platform_info() -> Dict[str, Any]:
    """
    Get comprehensive platform information.
    
    Returns:
        Dictionary with platform-specific system information including:
        - os: Platform name (linux/windows/macos/unknown)
        - os_release: OS release/version
        - machine: Hardware architecture
        - python: Python version
        - cpu_count: Number of CPU cores
        - platform_details: Platform-specific additional info
    """
    global _INFO_CACHE
    if _INFO_CACHE is not None:
        return _INFO_CACHE.copy()
    
    plat = detect_platform()
    
    base_info = {
        "os": plat,
        "os_release": platform.release(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "cpu_count": _get_cpu_count(),
    }
    
    # Platform-specific details
    if plat == "linux":
        from . import linux
        base_info["platform_details"] = linux.get_system_info()
    elif plat == "windows":
        from . import windows
        base_info["platform_details"] = windows.get_system_info()
    elif plat == "macos":
        from . import macos
        base_info["platform_details"] = macos.get_system_info()
    else:
        base_info["platform_details"] = {}
    
    _INFO_CACHE = base_info
    return base_info.copy()


def _get_cpu_count() -> Optional[int]:
    """Get CPU count safely."""
    try:
        import os
        return os.cpu_count()
    except Exception:
        return None


def clear_cache() -> None:
    """Clear platform detection cache (useful for testing)."""
    global _PLATFORM_CACHE, _INFO_CACHE
    _PLATFORM_CACHE = None
    _INFO_CACHE = None
