"""macOS-specific system information."""

from __future__ import annotations
import platform
import subprocess
from typing import Dict, Any, Optional


def get_system_info() -> Dict[str, Any]:
    """
    Get macOS-specific system information.
    
    Returns:
        Dictionary with macOS-specific details:
        - version: macOS version
        - version_name: Version codename (if available)
        - arch: Architecture (x86_64, arm64)
        - model: Mac model identifier
    """
    info = {
        "version": platform.mac_ver()[0],
        "version_name": get_version_name(),
        "arch": platform.machine(),
        "model": get_model_identifier(),
    }
    return info


def get_version_name() -> str:
    """
    Get macOS version codename.
    
    Returns:
        Version name (Sonoma, Ventura, etc.) or "unknown"
    """
    try:
        mac_ver = platform.mac_ver()[0]
        if mac_ver:
            major_minor = ".".join(mac_ver.split(".")[:2])
            version_names = {
                "14.": "Sonoma",
                "13.": "Ventura",
                "12.": "Monterey",
                "11.": "Big Sur",
                "10.15": "Catalina",
                "10.14": "Mojave",
                "10.13": "High Sierra",
            }
            
            for ver_prefix, name in version_names.items():
                if major_minor.startswith(ver_prefix.rstrip(".")):
                    return name
    except Exception:
        pass
    
    return "unknown"


def get_model_identifier() -> Optional[str]:
    """
    Get Mac model identifier (e.g., MacBookPro18,1).
    
    Returns:
        Model identifier string or None
    """
    try:
        result = subprocess.run(
            ["sysctl", "-n", "hw.model"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    
    return None


def get_memory_info() -> Optional[Dict[str, int]]:
    """
    Get memory information on macOS.
    
    Returns:
        Dictionary with memory info in bytes
    """
    try:
        result = subprocess.run(
            ["sysctl", "-n", "hw.memsize"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            total_bytes = int(result.stdout.strip())
            return {"total": total_bytes}
    except Exception:
        pass
    
    return None
