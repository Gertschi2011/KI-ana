from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class AddressBookEntrySnapshot:
    """Lightweight snapshot used by the chat v2 pipeline.

    This module is optional; on deployments without the addressbook boost feature,
    these helpers return empty values so the chat router can still load.
    """

    entry_id: int | None = None
    title: str = ""
    summary: str = ""
    meta: Dict[str, Any] = None  # type: ignore


def load_boost_blocks(*args, **kwargs) -> List[Dict[str, Any]]:
    return []


def match_entry_for_prompt(*args, **kwargs) -> Optional[AddressBookEntrySnapshot]:
    return None


def summarize_blocks_for_prompt(*args, **kwargs) -> Tuple[str, Dict[str, Any]]:
    return "", {}
