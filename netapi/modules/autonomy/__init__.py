"""
Autonomy Module
Resource management and self-preservation
"""
from .resource_monitor import ResourceMonitor, get_resource_monitor, EnergyMode

__all__ = ["ResourceMonitor", "get_resource_monitor", "EnergyMode"]
