"""
Addressbook Module
Provides hierarchical topic navigation for KI_ana's knowledge blocks
"""
from .router import router
from .indexer import AddressbookIndexer, build_addressbook_index

__all__ = ["router", "AddressbookIndexer", "build_addressbook_index"]
