"""
Audit System für KI_ana

Features:
- Block Validation Tracking
- Validator History
- Audit Trail
- Compliance Reports
"""
from __future__ import annotations
import time
import json
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from pathlib import Path
import sys

# Add system path
sys.path.insert(0, str(Path.home() / "ki_ana" / "system"))


@dataclass
class AuditEntry:
    """Audit trail entry."""
    entry_id: str
    timestamp: float
    event_type: str  # block_created, block_validated, block_rejected, etc.
    actor_id: str  # Device that performed the action
    target_id: str  # Block/Resource affected
    action: str
    details: Dict
    result: str  # success, failure
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class ValidationRecord:
    """Block validation record."""
    block_id: str
    validator_id: str
    timestamp: float
    is_valid: bool
    validation_details: Dict
    
    def to_dict(self) -> Dict:
        return asdict(self)


class AuditSystem:
    """
    Audit System for Compliance & Transparency.
    
    Singleton pattern.
    """
    
    _instance: Optional['AuditSystem'] = None
    
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
        
        # Audit trail
        self.audit_trail: List[AuditEntry] = []
        
        # Validation records
        self.validation_records: Dict[str, List[ValidationRecord]] = {}  # block_id -> records
        
        # Storage
        self.audit_dir = Path.home() / "ki_ana" / "data" / "audit"
        self.audit_dir.mkdir(parents=True, exist_ok=True)
        
        self.audit_file = self.audit_dir / "audit_trail.jsonl"
        
        # Load existing audit trail
        self._load_audit_trail()
        
        print(f"✅ Audit System initialized")
    
    def _load_audit_trail(self):
        """Load audit trail from file."""
        if self.audit_file.exists():
            try:
                with open(self.audit_file, 'r') as f:
                    for line in f:
                        entry_data = json.loads(line.strip())
                        entry = AuditEntry(**entry_data)
                        self.audit_trail.append(entry)
                print(f"📜 Loaded {len(self.audit_trail)} audit entries")
            except Exception as e:
                print(f"⚠️  Error loading audit trail: {e}")
    
    def _save_audit_entry(self, entry: AuditEntry):
        """Append audit entry to file."""
        try:
            with open(self.audit_file, 'a') as f:
                f.write(json.dumps(entry.to_dict()) + '\n')
        except Exception as e:
            print(f"⚠️  Error saving audit entry: {e}")
    
    def log_event(self, event_type: str, actor_id: str, target_id: str, 
                  action: str, details: Dict, result: str = "success") -> AuditEntry:
        """
        Log an audit event.
        
        Args:
            event_type: Type of event (block_created, block_validated, etc.)
            actor_id: Device that performed the action
            target_id: Block/Resource affected
            action: Description of action
            details: Additional details
            result: Result of action (success, failure)
        """
        entry = AuditEntry(
            entry_id=f"audit_{int(time.time())}_{len(self.audit_trail)}",
            timestamp=time.time(),
            event_type=event_type,
            actor_id=actor_id,
            target_id=target_id,
            action=action,
            details=details,
            result=result
        )
        
        self.audit_trail.append(entry)
        self._save_audit_entry(entry)
        
        return entry
    
    def log_block_validation(self, block_id: str, validator_id: str, 
                            is_valid: bool, details: Dict):
        """Log block validation."""
        record = ValidationRecord(
            block_id=block_id,
            validator_id=validator_id,
            timestamp=time.time(),
            is_valid=is_valid,
            validation_details=details
        )
        
        if block_id not in self.validation_records:
            self.validation_records[block_id] = []
        
        self.validation_records[block_id].append(record)
        
        # Also log as audit event
        self.log_event(
            event_type="block_validated",
            actor_id=validator_id,
            target_id=block_id,
            action=f"Validated block: {'valid' if is_valid else 'invalid'}",
            details=details,
            result="success" if is_valid else "failure"
        )
        
        print(f"✅ Validation logged: {block_id[:8]}... by {validator_id[:8]}...")
    
    def get_block_validators(self, block_id: str) -> List[ValidationRecord]:
        """Get all validators for a block."""
        return self.validation_records.get(block_id, [])
    
    def get_validator_history(self, validator_id: str) -> List[ValidationRecord]:
        """Get validation history for a validator."""
        history = []
        for records in self.validation_records.values():
            history.extend([r for r in records if r.validator_id == validator_id])
        return sorted(history, key=lambda x: x.timestamp, reverse=True)
    
    def get_audit_trail(self, event_type: str = None, actor_id: str = None,
                       start_time: float = None, end_time: float = None,
                       limit: int = 100) -> List[AuditEntry]:
        """
        Get filtered audit trail.
        
        Args:
            event_type: Filter by event type
            actor_id: Filter by actor
            start_time: Filter by start time
            end_time: Filter by end time
            limit: Maximum number of entries
        """
        entries = self.audit_trail
        
        # Apply filters
        if event_type:
            entries = [e for e in entries if e.event_type == event_type]
        
        if actor_id:
            entries = [e for e in entries if e.actor_id == actor_id]
        
        if start_time:
            entries = [e for e in entries if e.timestamp >= start_time]
        
        if end_time:
            entries = [e for e in entries if e.timestamp <= end_time]
        
        # Sort by timestamp (newest first)
        entries = sorted(entries, key=lambda x: x.timestamp, reverse=True)
        
        # Apply limit
        return entries[:limit]
    
    def generate_compliance_report(self, start_time: float = None, 
                                   end_time: float = None) -> Dict:
        """
        Generate compliance report.
        
        Returns statistics and summary of audit trail.
        """
        # Filter entries by time
        entries = self.get_audit_trail(start_time=start_time, end_time=end_time, limit=None)
        
        # Count by event type
        event_counts = {}
        for entry in entries:
            event_counts[entry.event_type] = event_counts.get(entry.event_type, 0) + 1
        
        # Count by actor
        actor_counts = {}
        for entry in entries:
            actor_counts[entry.actor_id] = actor_counts.get(entry.actor_id, 0) + 1
        
        # Count by result
        success_count = sum(1 for e in entries if e.result == "success")
        failure_count = sum(1 for e in entries if e.result == "failure")
        
        # Validation statistics
        total_validations = len([e for e in entries if e.event_type == "block_validated"])
        valid_blocks = len([e for e in entries if e.event_type == "block_validated" and e.result == "success"])
        invalid_blocks = total_validations - valid_blocks
        
        return {
            "report_generated": time.time(),
            "period": {
                "start": start_time or min((e.timestamp for e in entries), default=0),
                "end": end_time or max((e.timestamp for e in entries), default=time.time())
            },
            "total_events": len(entries),
            "event_types": event_counts,
            "actors": actor_counts,
            "results": {
                "success": success_count,
                "failure": failure_count,
                "success_rate": success_count / len(entries) if entries else 0
            },
            "validations": {
                "total": total_validations,
                "valid": valid_blocks,
                "invalid": invalid_blocks,
                "validation_rate": valid_blocks / total_validations if total_validations > 0 else 0
            }
        }
    
    def get_stats(self) -> Dict:
        """Get audit system statistics."""
        return {
            "total_audit_entries": len(self.audit_trail),
            "blocks_with_validations": len(self.validation_records),
            "total_validations": sum(len(records) for records in self.validation_records.values()),
            "unique_validators": len(set(
                r.validator_id 
                for records in self.validation_records.values() 
                for r in records
            ))
        }


# Singleton
_system: Optional[AuditSystem] = None


def get_audit_system() -> AuditSystem:
    """Get singleton audit system."""
    global _system
    if _system is None:
        _system = AuditSystem()
    return _system


if __name__ == "__main__":
    print("📋 Audit System Test\n")
    
    audit = get_audit_system()
    
    # Log some events
    print("1️⃣ Logging events...")
    audit.log_event("block_created", "device-1", "block-123", "Created new block", {"topic": "test"})
    audit.log_block_validation("block-123", "device-2", True, {"hash_valid": True})
    audit.log_block_validation("block-123", "device-3", True, {"hash_valid": True})
    
    # Get validators
    print("\n2️⃣ Block validators:")
    validators = audit.get_block_validators("block-123")
    print(f"   Block-123 validated by {len(validators)} validator(s)")
    
    # Get audit trail
    print("\n3️⃣ Audit trail:")
    trail = audit.get_audit_trail(limit=5)
    for entry in trail:
        print(f"   [{entry.event_type}] {entry.action} by {entry.actor_id[:8]}...")
    
    # Generate report
    print("\n4️⃣ Compliance report:")
    report = audit.generate_compliance_report()
    print(f"   Total events: {report['total_events']}")
    print(f"   Success rate: {report['results']['success_rate']:.1%}")
    print(f"   Validations: {report['validations']['total']}")
    
    # Stats
    print("\n5️⃣ Stats:")
    stats = audit.get_stats()
    for key, value in stats.items():
        print(f"   {key}: {value}")
    
    print("\n✅ Audit System test complete!")
