"""
Lifecycle Engine - Subjective Time for KI_ana
Phase 9 - TimeFlow 2.0
"""
import json
import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from collections import defaultdict


CONFIG_FILE = Path("/home/kiana/ki_ana/data/timeflow_config.json")
STATE_FILE = Path("/home/kiana/ki_ana/data/lifecycle_state.json")
DIARY_DIR = Path("/home/kiana/ki_ana/data/time_diary")


class LifecycleEngine:
    """Tracks KI_ana's subjective lifecycle"""
    
    def __init__(self):
        self.config = self._load_config()
        self.state = self._load_state()
        DIARY_DIR.mkdir(parents=True, exist_ok=True)
    
    def _load_config(self) -> Dict[str, Any]:
        """Load lifecycle configuration"""
        if not CONFIG_FILE.exists():
            return self._get_default_config()
        
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Default config if file not found"""
        return {
            "lifecycle": {
                "cycle_types": {},
                "age_calculation": {"method": "weighted_cycles"}
            }
        }
    
    def _load_state(self) -> Dict[str, Any]:
        """Load current lifecycle state"""
        if not STATE_FILE.exists():
            return self._init_state()
        
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return self._init_state()
    
    def _init_state(self) -> Dict[str, Any]:
        """Initialize lifecycle state"""
        birth_time = int(time.time())
        
        return {
            "birth_timestamp": birth_time,
            "total_cycles": 0,
            "weighted_cycles": 0.0,
            "cycle_counts": {
                "audit": 0,
                "mirror": 0,
                "dialog": 0,
                "reflection": 0,
                "creation": 0
            },
            "current_phase": "infant",
            "last_reflection": birth_time,
            "diary_entries": 0,
            "compressed_memories": 0
        }
    
    def _save_state(self):
        """Save lifecycle state"""
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.state, f, ensure_ascii=False, indent=2)
    
    def record_cycle(
        self,
        cycle_type: str,
        duration_ms: int = 0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Record a lifecycle cycle
        
        Args:
            cycle_type: Type of cycle (audit, mirror, dialog, etc.)
            duration_ms: Duration in milliseconds
            metadata: Additional metadata
        
        Returns:
            Cycle record
        """
        # Get cycle weight
        cycle_config = self.config.get('lifecycle', {}).get('cycle_types', {})
        weight = cycle_config.get(cycle_type, {}).get('weight', 1.0)
        
        # Update counters
        self.state["total_cycles"] += 1
        self.state["weighted_cycles"] += weight
        
        if cycle_type in self.state["cycle_counts"]:
            self.state["cycle_counts"][cycle_type] += 1
        
        # Check for phase transition
        old_phase = self.state["current_phase"]
        new_phase = self._calculate_phase()
        phase_changed = old_phase != new_phase
        
        if phase_changed:
            self.state["current_phase"] = new_phase
        
        # Create diary entry
        entry = self._create_diary_entry(
            cycle_type,
            weight,
            duration_ms,
            metadata or {},
            phase_changed
        )
        
        self.state["diary_entries"] += 1
        
        # Save state
        self._save_state()
        
        return entry
    
    def _calculate_phase(self) -> str:
        """Calculate current life phase based on cycles"""
        weighted = self.state["weighted_cycles"]
        
        phases = self.config.get('lifecycle', {}).get('age_calculation', {}).get('phases', {})
        
        for phase_name, phase_config in sorted(
            phases.items(),
            key=lambda x: x[1].get('max_cycles') if x[1].get('max_cycles') is not None else float('inf')
        ):
            max_cycles = phase_config.get('max_cycles')
            
            if max_cycles is None or weighted < max_cycles:
                return phase_name
        
        return "ancient"
    
    def _create_diary_entry(
        self,
        cycle_type: str,
        weight: float,
        duration_ms: int,
        metadata: Dict[str, Any],
        phase_changed: bool
    ) -> Dict[str, Any]:
        """Create a time diary entry"""
        timestamp = int(time.time())
        cycle_num = self.state["total_cycles"]
        
        entry = {
            "id": f"timeflow_{timestamp}_{cycle_num}",
            "type": "timeflow_entry",
            "cycle_type": cycle_type,
            "cycle_number": cycle_num,
            "weighted_contribution": weight,
            "timestamp": timestamp,
            "duration_ms": duration_ms,
            "phase": self.state["current_phase"],
            "phase_transition": phase_changed,
            "metadata": metadata
        }
        
        # Save to diary
        diary_file = DIARY_DIR / f"entry_{timestamp}_{cycle_num}.json"
        
        with open(diary_file, 'w', encoding='utf-8') as f:
            json.dump(entry, f, ensure_ascii=False, indent=2)
        
        return entry
    
    def get_age(self) -> Dict[str, Any]:
        """
        Get KI_ana's age in various formats
        
        Returns:
            Age information
        """
        birth = self.state["birth_timestamp"]
        now = int(time.time())
        
        # Chronological age
        age_seconds = now - birth
        age_days = age_seconds / 86400
        
        # Cycle age
        total_cycles = self.state["total_cycles"]
        weighted_cycles = self.state["weighted_cycles"]
        
        # Subjective age
        baseline = self.config.get('lifecycle', {}).get('age_calculation', {}).get(
            'baseline_cycles_per_day', 100
        )
        subjective_days = weighted_cycles / baseline
        
        # Phase
        phase = self.state["current_phase"]
        phases = self.config.get('lifecycle', {}).get('age_calculation', {}).get('phases', {})
        phase_label = phases.get(phase, {}).get('label', phase)
        
        return {
            "chronological": {
                "seconds": age_seconds,
                "days": round(age_days, 2),
                "human_readable": self._format_duration(age_seconds)
            },
            "cycles": {
                "total": total_cycles,
                "weighted": round(weighted_cycles, 2),
                "by_type": self.state["cycle_counts"]
            },
            "subjective": {
                "days": round(subjective_days, 2),
                "phase": phase,
                "phase_label": phase_label
            },
            "born_at": datetime.fromtimestamp(birth).isoformat(),
            "current_time": datetime.fromtimestamp(now).isoformat()
        }
    
    def _format_duration(self, seconds: int) -> str:
        """Format duration in human-readable form"""
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            return f"{seconds // 60}m"
        elif seconds < 86400:
            return f"{seconds // 3600}h"
        else:
            days = seconds // 86400
            return f"{days}d"
    
    def get_lifecycle_summary(self) -> Dict[str, Any]:
        """Get complete lifecycle summary"""
        age = self.get_age()
        
        return {
            "age": age,
            "diary_entries": self.state["diary_entries"],
            "compressed_memories": self.state["compressed_memories"],
            "last_reflection": datetime.fromtimestamp(
                self.state["last_reflection"]
            ).isoformat(),
            "vitality": self._calculate_vitality()
        }
    
    def _calculate_vitality(self) -> Dict[str, Any]:
        """Calculate current vitality metrics"""
        # Recent activity
        recent_cycles = self._count_recent_cycles(hours=24)
        
        # Distribution
        total = sum(self.state["cycle_counts"].values())
        if total == 0:
            distribution = {}
        else:
            distribution = {
                k: round(v / total, 2)
                for k, v in self.state["cycle_counts"].items()
            }
        
        return {
            "recent_activity_24h": recent_cycles,
            "cycle_distribution": distribution,
            "total_experience": self.state["weighted_cycles"]
        }
    
    def _count_recent_cycles(self, hours: int = 24) -> int:
        """Count cycles in recent period"""
        cutoff = int(time.time()) - (hours * 3600)
        count = 0
        
        # Count recent diary entries
        for entry_file in DIARY_DIR.glob("entry_*.json"):
            try:
                with open(entry_file, 'r', encoding='utf-8') as f:
                    entry = json.load(f)
                    if entry.get('timestamp', 0) > cutoff:
                        count += 1
            except:
                pass
        
        return count


# Singleton
_engine = None


def get_lifecycle_engine() -> LifecycleEngine:
    """Get singleton lifecycle engine"""
    global _engine
    if _engine is None:
        _engine = LifecycleEngine()
    return _engine


if __name__ == "__main__":
    # Test
    engine = LifecycleEngine()
    
    # Record some cycles
    engine.record_cycle("audit", duration_ms=2340)
    engine.record_cycle("dialog", duration_ms=150)
    engine.record_cycle("reflection", duration_ms=5000)
    
    # Get age
    age = engine.get_age()
    print("Age:", json.dumps(age, indent=2))
    
    # Get summary
    summary = engine.get_lifecycle_summary()
    print("\nSummary:", json.dumps(summary, indent=2))
