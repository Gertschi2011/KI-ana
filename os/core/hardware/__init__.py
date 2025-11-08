"""
KI-ana OS - Hardware Intelligence Module

Intelligent hardware detection, profiling, and optimization.
"""

from .scanner import HardwareScanner
from .optimizer import HardwareOptimizer
from .profiler import HardwareProfiler

__all__ = ["HardwareScanner", "HardwareOptimizer", "HardwareProfiler"]
