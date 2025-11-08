"""
Ethic Module
Provides ethical guidelines and response checking
"""
from .middleware import EthicEngine, get_ethic_engine, apply_ethics

__all__ = ["EthicEngine", "get_ethic_engine", "apply_ethics"]
