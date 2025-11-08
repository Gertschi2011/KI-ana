"""Platform-specific OS implementations."""

from .detector import detect_platform, get_platform_info

__all__ = ["detect_platform", "get_platform_info"]
