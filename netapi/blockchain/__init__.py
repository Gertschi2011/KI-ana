"""
Blockchain Module - Immutable Knowledge Storage

Provides blockchain-based storage for tamper-proof knowledge records.
"""
from .knowledge_chain import KnowledgeChain, Block, get_knowledge_chain

__all__ = [
    "KnowledgeChain",
    "Block",
    "get_knowledge_chain",
]
