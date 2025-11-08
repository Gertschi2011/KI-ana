"""Windows-specific system information."""

from __future__ import annotations
import platform
from typing import Dict, Any


def get_system_info() -> Dict[str, Any]:
    """
    Get Windows-specific system information.
    
    Returns:
        Dictionary with Windows-specific details:
        - version: Windows version
        - edition: Windows edition (if available)
        - build: Build number
        - service_pack: Service pack (if any)
    """
    info = {
        "version": platform.version(),
        "edition": get_edition(),
        "build": get_build_number(),
        "service_pack": get_service_pack(),
    }
    return info


def get_edition() -> str:
    """
    Get Windows edition (Home, Pro, Enterprise, etc.).
    
    Returns:
        Edition string or "unknown"
    """
    try:
        if hasattr(platform, 'win32_edition'):
            edition = platform.win32_edition()
            if edition:
                return edition
    except Exception:
        pass
    
    return "unknown"


def get_build_number() -> str:
    """
    Get Windows build number.
    
    Returns:
        Build number string
    """
    try:
        win_ver = platform.win32_ver()
        if win_ver and len(win_ver) > 1:
            return win_ver[1] or "unknown"
    except Exception:
        pass
    
    return "unknown"


def get_service_pack() -> str:
    """
    Get Windows service pack information.
    
    Returns:
        Service pack string or empty string
    """
    try:
        win_ver = platform.win32_ver()
        if win_ver and len(win_ver) > 2:
            return win_ver[2] or ""
    except Exception:
        pass
    
    return ""


def get_memory_info() -> Dict[str, int]:
    """
    Get memory information on Windows.
    
    Returns:
        Dictionary with memory info in bytes
    """
    try:
        import ctypes
        
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]
        
        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(stat)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
        
        return {
            "total": stat.ullTotalPhys,
            "available": stat.ullAvailPhys,
        }
    except Exception:
        return {}
