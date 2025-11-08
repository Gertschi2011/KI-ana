"""Linux-specific system information."""

from __future__ import annotations
import platform
import subprocess
from typing import Dict, Any, Optional
from pathlib import Path


def get_system_info() -> Dict[str, Any]:
    """
    Get Linux-specific system information.
    
    Returns:
        Dictionary with Linux-specific details:
        - distro: Distribution name (ubuntu, debian, arch, etc.)
        - distro_version: Distribution version
        - kernel: Kernel version
        - desktop: Desktop environment (if detectable)
        - libc: C library version
    """
    info = {
        "distro": get_distro(),
        "distro_version": get_distro_version(),
        "kernel": platform.release(),
        "desktop": get_desktop_environment(),
        "libc": get_libc_version(),
    }
    return info


def get_distro() -> str:
    """
    Detect Linux distribution.
    
    Returns:
        Distribution identifier (ubuntu, debian, fedora, arch, etc.)
    """
    try:
        # Try /etc/os-release first (standard)
        os_release = Path("/etc/os-release")
        if os_release.exists():
            with open(os_release) as f:
                for line in f:
                    if line.startswith("ID="):
                        distro = line.split("=")[1].strip().strip('"').strip("'")
                        return distro.lower()
    except Exception:
        pass
    
    # Fallback: check specific release files
    release_files = {
        "/etc/debian_version": "debian",
        "/etc/redhat-release": "redhat",
        "/etc/arch-release": "arch",
        "/etc/gentoo-release": "gentoo",
    }
    
    for file_path, distro in release_files.items():
        if Path(file_path).exists():
            return distro
    
    return "unknown"


def get_distro_version() -> str:
    """
    Get Linux distribution version.
    
    Returns:
        Version string (e.g., "22.04", "11", "rolling")
    """
    try:
        os_release = Path("/etc/os-release")
        if os_release.exists():
            with open(os_release) as f:
                for line in f:
                    if line.startswith("VERSION_ID="):
                        version = line.split("=")[1].strip().strip('"').strip("'")
                        return version
    except Exception:
        pass
    
    return "unknown"


def get_desktop_environment() -> Optional[str]:
    """
    Detect desktop environment.
    
    Returns:
        Desktop environment name (gnome, kde, xfce, etc.) or None
    """
    import os
    
    # Check environment variables
    de_vars = [
        ("GNOME_DESKTOP_SESSION_ID", "gnome"),
        ("KDE_FULL_SESSION", "kde"),
        ("DESKTOP_SESSION", None),  # Use value directly
        ("XDG_CURRENT_DESKTOP", None),  # Use value directly
    ]
    
    for var, de_name in de_vars:
        value = os.environ.get(var)
        if value:
            if de_name:
                return de_name
            else:
                return value.lower()
    
    return None


def get_libc_version() -> str:
    """
    Get C library version.
    
    Returns:
        libc version string (e.g., "glibc 2.35")
    """
    try:
        libc = platform.libc_ver()
        if libc[0] and libc[1]:
            return f"{libc[0]} {libc[1]}"
    except Exception:
        pass
    
    return "unknown"


def get_memory_info() -> Optional[Dict[str, int]]:
    """
    Get memory information from /proc/meminfo.
    
    Returns:
        Dictionary with memory info in bytes:
        - total: Total physical memory
        - available: Available memory
        - free: Free memory
    """
    try:
        meminfo = {}
        with open("/proc/meminfo") as f:
            for line in f:
                parts = line.split(":")
                if len(parts) == 2:
                    key = parts[0].strip()
                    value_str = parts[1].strip().split()[0]  # Remove "kB"
                    try:
                        value_kb = int(value_str)
                        if key in ("MemTotal", "MemAvailable", "MemFree"):
                            meminfo[key.lower().replace("mem", "")] = value_kb * 1024  # Convert to bytes
                    except ValueError:
                        continue
        
        if meminfo:
            return meminfo
    except Exception:
        pass
    
    return None


def get_gpu_info() -> list[Dict[str, str]]:
    """
    Detect GPU information using nvidia-smi or other tools.
    
    Returns:
        List of GPU info dictionaries
    """
    gpus = []
    
    # Try nvidia-smi
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                if line:
                    parts = line.split(",")
                    if len(parts) >= 2:
                        gpus.append({
                            "vendor": "nvidia",
                            "name": parts[0].strip(),
                            "driver": parts[1].strip(),
                        })
    except Exception:
        pass
    
    # Try lspci for AMD/Intel
    if not gpus:
        try:
            result = subprocess.run(
                ["lspci", "-nn"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                for line in result.stdout.split("\n"):
                    if "VGA compatible controller" in line or "3D controller" in line:
                        gpus.append({
                            "vendor": "unknown",
                            "name": line.split(":", 2)[-1].strip() if ":" in line else line,
                            "driver": "unknown",
                        })
        except Exception:
            pass
    
    return gpus
