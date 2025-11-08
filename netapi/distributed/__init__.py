"""
Distributed Module - Sub-KI Network

Provides distributed processing across specialized AI instances.
"""
from .submind_network import SubMindNetwork, SubMind, SubMindRole, DistributedTask, get_submind_network

__all__ = [
    "SubMindNetwork",
    "SubMind",
    "SubMindRole",
    "DistributedTask",
    "get_submind_network",
]
