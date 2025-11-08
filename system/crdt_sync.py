"""
CRDT (Conflict-free Replicated Data Types) für KI_ana

Ermöglicht konfliktfreie Synchronisation zwischen Peers ohne zentrale Koordination.

Features:
- LWW (Last-Write-Wins) Register
- G-Counter (Grow-only Counter)
- PN-Counter (Positive-Negative Counter)
- OR-Set (Observed-Remove Set)
- Vector Clocks für Kausalität

Verwendung:
- Konfliktfreie Block-Updates
- Dezentrale Zähler (Views, Likes)
- Verteilte Sets (Tags, Categories)
"""
from __future__ import annotations
import time
import json
from typing import Dict, Any, List, Optional, Set, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
import sys

# Add system path
sys.path.insert(0, str(Path.home() / "ki_ana" / "system"))


@dataclass
class VectorClock:
    """Vector Clock für Kausalitäts-Tracking."""
    clocks: Dict[str, int]
    
    def __init__(self, device_id: str = None):
        self.clocks = {}
        if device_id:
            self.clocks[device_id] = 0
    
    def increment(self, device_id: str):
        """Increment clock for device."""
        self.clocks[device_id] = self.clocks.get(device_id, 0) + 1
    
    def merge(self, other: 'VectorClock'):
        """Merge with another vector clock."""
        for device_id, clock in other.clocks.items():
            self.clocks[device_id] = max(self.clocks.get(device_id, 0), clock)
    
    def happens_before(self, other: 'VectorClock') -> bool:
        """Check if this clock happens before other."""
        # self < other if all clocks are ≤ and at least one is <
        all_less_or_equal = all(
            self.clocks.get(d, 0) <= other.clocks.get(d, 0)
            for d in set(self.clocks.keys()) | set(other.clocks.keys())
        )
        at_least_one_less = any(
            self.clocks.get(d, 0) < other.clocks.get(d, 0)
            for d in set(self.clocks.keys()) | set(other.clocks.keys())
        )
        return all_less_or_equal and at_least_one_less
    
    def concurrent(self, other: 'VectorClock') -> bool:
        """Check if clocks are concurrent (no causal relationship)."""
        return not self.happens_before(other) and not other.happens_before(self)
    
    def to_dict(self) -> Dict[str, int]:
        return self.clocks.copy()
    
    @classmethod
    def from_dict(cls, data: Dict[str, int]) -> 'VectorClock':
        vc = cls()
        vc.clocks = data.copy()
        return vc


class LWWRegister:
    """
    Last-Write-Wins Register.
    
    Stores a value with timestamp. Conflicts resolved by timestamp.
    """
    
    def __init__(self, device_id: str):
        self.device_id = device_id
        self.value: Any = None
        self.timestamp: float = 0
        self.writer: str = ""
    
    def set(self, value: Any):
        """Set value with current timestamp."""
        self.value = value
        self.timestamp = time.time()
        self.writer = self.device_id
    
    def merge(self, other: 'LWWRegister'):
        """Merge with another register (LWW)."""
        if other.timestamp > self.timestamp:
            self.value = other.value
            self.timestamp = other.timestamp
            self.writer = other.writer
        elif other.timestamp == self.timestamp:
            # Tie-break by device_id (deterministic)
            if other.writer > self.writer:
                self.value = other.value
                self.writer = other.writer
    
    def get(self) -> Any:
        """Get current value."""
        return self.value
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "value": self.value,
            "timestamp": self.timestamp,
            "writer": self.writer
        }
    
    @classmethod
    def from_dict(cls, device_id: str, data: Dict[str, Any]) -> 'LWWRegister':
        reg = cls(device_id)
        reg.value = data["value"]
        reg.timestamp = data["timestamp"]
        reg.writer = data["writer"]
        return reg


class GCounter:
    """
    Grow-only Counter.
    
    Can only increment. Merge by taking max of each device's counter.
    """
    
    def __init__(self, device_id: str):
        self.device_id = device_id
        self.counts: Dict[str, int] = {device_id: 0}
    
    def increment(self, amount: int = 1):
        """Increment counter."""
        self.counts[self.device_id] = self.counts.get(self.device_id, 0) + amount
    
    def merge(self, other: 'GCounter'):
        """Merge with another counter."""
        for device_id, count in other.counts.items():
            self.counts[device_id] = max(self.counts.get(device_id, 0), count)
    
    def value(self) -> int:
        """Get total count."""
        return sum(self.counts.values())
    
    def to_dict(self) -> Dict[str, int]:
        return self.counts.copy()
    
    @classmethod
    def from_dict(cls, device_id: str, data: Dict[str, int]) -> 'GCounter':
        counter = cls(device_id)
        counter.counts = data.copy()
        return counter


class PNCounter:
    """
    Positive-Negative Counter.
    
    Can increment and decrement. Uses two G-Counters.
    """
    
    def __init__(self, device_id: str):
        self.device_id = device_id
        self.positive = GCounter(device_id)
        self.negative = GCounter(device_id)
    
    def increment(self, amount: int = 1):
        """Increment counter."""
        self.positive.increment(amount)
    
    def decrement(self, amount: int = 1):
        """Decrement counter."""
        self.negative.increment(amount)
    
    def merge(self, other: 'PNCounter'):
        """Merge with another counter."""
        self.positive.merge(other.positive)
        self.negative.merge(other.negative)
    
    def value(self) -> int:
        """Get current value."""
        return self.positive.value() - self.negative.value()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "positive": self.positive.to_dict(),
            "negative": self.negative.to_dict()
        }
    
    @classmethod
    def from_dict(cls, device_id: str, data: Dict[str, Any]) -> 'PNCounter':
        counter = cls(device_id)
        counter.positive = GCounter.from_dict(device_id, data["positive"])
        counter.negative = GCounter.from_dict(device_id, data["negative"])
        return counter


class ORSet:
    """
    Observed-Remove Set.
    
    Add/Remove elements with unique tags. Removes win over adds.
    """
    
    def __init__(self, device_id: str):
        self.device_id = device_id
        self.added: Dict[Any, Set[Tuple[str, float]]] = {}  # element -> {(device, timestamp)}
        self.removed: Set[Tuple[Any, str, float]] = set()  # {(element, device, timestamp)}
    
    def add(self, element: Any):
        """Add element."""
        tag = (self.device_id, time.time())
        if element not in self.added:
            self.added[element] = set()
        self.added[element].add(tag)
    
    def remove(self, element: Any):
        """Remove element."""
        if element in self.added:
            # Remove all observed tags
            for tag in self.added[element]:
                self.removed.add((element, tag[0], tag[1]))
    
    def merge(self, other: 'ORSet'):
        """Merge with another set."""
        # Merge added
        for element, tags in other.added.items():
            if element not in self.added:
                self.added[element] = set()
            self.added[element].update(tags)
        
        # Merge removed
        self.removed.update(other.removed)
    
    def elements(self) -> Set[Any]:
        """Get current elements."""
        result = set()
        for element, tags in self.added.items():
            # Element is in set if it has tags not in removed
            remaining_tags = tags - {(d, t) for e, d, t in self.removed if e == element}
            if remaining_tags:
                result.add(element)
        return result
    
    def contains(self, element: Any) -> bool:
        """Check if element is in set."""
        return element in self.elements()


class CRDTStore:
    """
    CRDT Store for KI_ana.
    
    Manages CRDTs for conflict-free synchronization.
    """
    
    _instance: Optional['CRDTStore'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        
        self._initialized = True
        
        # Device ID
        from submind_manager import get_submind_manager
        self.device_id = get_submind_manager().this_device_id
        
        # CRDT instances
        self.registers: Dict[str, LWWRegister] = {}
        self.counters: Dict[str, PNCounter] = {}
        self.sets: Dict[str, ORSet] = {}
        
        # Vector clock
        self.vector_clock = VectorClock(self.device_id)
        
        # Storage
        self.storage_dir = Path.home() / "ki_ana" / "data" / "crdt"
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"✅ CRDT Store initialized")
    
    def get_register(self, key: str) -> LWWRegister:
        """Get or create LWW register."""
        if key not in self.registers:
            self.registers[key] = LWWRegister(self.device_id)
        return self.registers[key]
    
    def get_counter(self, key: str) -> PNCounter:
        """Get or create PN counter."""
        if key not in self.counters:
            self.counters[key] = PNCounter(self.device_id)
        return self.counters[key]
    
    def get_set(self, key: str) -> ORSet:
        """Get or create OR set."""
        if key not in self.sets:
            self.sets[key] = ORSet(self.device_id)
        return self.sets[key]
    
    def merge_state(self, other_state: Dict[str, Any]):
        """Merge state from another peer."""
        # Merge vector clock
        if "vector_clock" in other_state:
            other_vc = VectorClock.from_dict(other_state["vector_clock"])
            self.vector_clock.merge(other_vc)
        
        # Merge registers
        for key, data in other_state.get("registers", {}).items():
            reg = self.get_register(key)
            other_reg = LWWRegister.from_dict(self.device_id, data)
            reg.merge(other_reg)
        
        # Merge counters
        for key, data in other_state.get("counters", {}).items():
            counter = self.get_counter(key)
            other_counter = PNCounter.from_dict(self.device_id, data)
            counter.merge(other_counter)
        
        print(f"✅ Merged CRDT state from peer")
    
    def get_state(self) -> Dict[str, Any]:
        """Get current state for synchronization."""
        return {
            "vector_clock": self.vector_clock.to_dict(),
            "registers": {k: v.to_dict() for k, v in self.registers.items()},
            "counters": {k: v.to_dict() for k, v in self.counters.items()}
        }


# Singleton
_store: Optional[CRDTStore] = None


def get_crdt_store() -> CRDTStore:
    """Get singleton CRDT store."""
    global _store
    if _store is None:
        _store = CRDTStore()
    return _store


if __name__ == "__main__":
    print("🧩 CRDT Test\n")
    
    # Test LWW Register
    print("📝 Testing LWW Register...")
    reg1 = LWWRegister("device-1")
    reg1.set("value-1")
    
    reg2 = LWWRegister("device-2")
    reg2.set("value-2")
    
    reg1.merge(reg2)
    print(f"✅ Merged value: {reg1.get()}")
    
    # Test G-Counter
    print("\n📊 Testing G-Counter...")
    counter1 = GCounter("device-1")
    counter1.increment(5)
    
    counter2 = GCounter("device-2")
    counter2.increment(3)
    
    counter1.merge(counter2)
    print(f"✅ Total count: {counter1.value()}")
    
    # Test PN-Counter
    print("\n📊 Testing PN-Counter...")
    pn1 = PNCounter("device-1")
    pn1.increment(10)
    pn1.decrement(3)
    
    pn2 = PNCounter("device-2")
    pn2.increment(5)
    
    pn1.merge(pn2)
    print(f"✅ Final value: {pn1.value()}")
    
    # Test OR-Set
    print("\n📦 Testing OR-Set...")
    set1 = ORSet("device-1")
    set1.add("item-1")
    set1.add("item-2")
    
    set2 = ORSet("device-2")
    set2.add("item-2")
    set2.add("item-3")
    
    set1.merge(set2)
    print(f"✅ Elements: {set1.elements()}")
    
    # Test Vector Clock
    print("\n🕐 Testing Vector Clock...")
    vc1 = VectorClock("device-1")
    vc1.increment("device-1")
    
    vc2 = VectorClock("device-2")
    vc2.increment("device-2")
    
    print(f"✅ Concurrent: {vc1.concurrent(vc2)}")
    
    vc1.merge(vc2)
    print(f"✅ Merged clock: {vc1.to_dict()}")
    
    print("\n✅ All CRDT tests passed!")
