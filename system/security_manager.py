"""
Security Manager für KI_ana

Features:
- Rate Limiting
- Anomalie-Erkennung
- Abuse-Detection
- Emergency Override
- Audit Logging
"""
from __future__ import annotations
import time
import hashlib
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict, deque
from pathlib import Path
import json
import sys

# Add system path
sys.path.insert(0, str(Path.home() / "ki_ana" / "system"))


@dataclass
class RateLimitConfig:
    """Rate limit configuration."""
    max_requests: int
    window_seconds: int


@dataclass
class AuditLog:
    """Audit log entry."""
    timestamp: float
    event_type: str
    user_id: str
    action: str
    details: Dict
    severity: str  # info, warning, critical


class RateLimiter:
    """Rate limiter for API endpoints."""
    
    def __init__(self):
        self.requests: Dict[str, deque] = defaultdict(deque)
        self.configs: Dict[str, RateLimitConfig] = {
            "default": RateLimitConfig(100, 60),  # 100 req/min
            "messaging": RateLimitConfig(50, 60),  # 50 msg/min
            "blocks": RateLimitConfig(30, 60),  # 30 blocks/min
        }
    
    def check_limit(self, key: str, endpoint: str = "default") -> Tuple[bool, int]:
        """
        Check if request is within rate limit.
        
        Returns: (allowed, remaining)
        """
        config = self.configs.get(endpoint, self.configs["default"])
        now = time.time()
        
        # Clean old requests
        while self.requests[key] and self.requests[key][0] < now - config.window_seconds:
            self.requests[key].popleft()
        
        # Check limit
        if len(self.requests[key]) >= config.max_requests:
            return False, 0
        
        # Add request
        self.requests[key].append(now)
        remaining = config.max_requests - len(self.requests[key])
        
        return True, remaining


class AnomalyDetector:
    """Detect anomalous behavior."""
    
    def __init__(self):
        self.baselines: Dict[str, List[float]] = defaultdict(list)
        self.alerts: List[Dict] = []
    
    def record_metric(self, metric_name: str, value: float):
        """Record a metric value."""
        self.baselines[metric_name].append(value)
        
        # Keep only last 100 values
        if len(self.baselines[metric_name]) > 100:
            self.baselines[metric_name].pop(0)
    
    def detect_anomaly(self, metric_name: str, value: float, threshold: float = 3.0) -> bool:
        """
        Detect if value is anomalous (z-score > threshold).
        
        Returns True if anomalous.
        """
        if metric_name not in self.baselines or len(self.baselines[metric_name]) < 10:
            return False
        
        values = self.baselines[metric_name]
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        std_dev = variance ** 0.5
        
        if std_dev == 0:
            return False
        
        z_score = abs((value - mean) / std_dev)
        
        if z_score > threshold:
            self.alerts.append({
                "metric": metric_name,
                "value": value,
                "z_score": z_score,
                "timestamp": time.time()
            })
            return True
        
        return False


class SecurityManager:
    """
    Central Security Manager.
    
    Singleton pattern.
    """
    
    _instance: Optional['SecurityManager'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        
        self._initialized = True
        
        # Components
        self.rate_limiter = RateLimiter()
        self.anomaly_detector = AnomalyDetector()
        
        # Audit log
        self.audit_log: List[AuditLog] = []
        self.audit_file = Path.home() / "ki_ana" / "data" / "audit.log"
        self.audit_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Emergency override
        self.emergency_hash = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"  # SHA256 of empty string (placeholder)
        
        # Blacklist
        self.blacklist: set = set()
        
        print(f"✅ Security Manager initialized")
    
    def check_rate_limit(self, user_id: str, endpoint: str = "default") -> Tuple[bool, int]:
        """Check rate limit for user."""
        return self.rate_limiter.check_limit(user_id, endpoint)
    
    def detect_anomaly(self, metric_name: str, value: float) -> bool:
        """Detect anomalous behavior."""
        self.anomaly_detector.record_metric(metric_name, value)
        is_anomaly = self.anomaly_detector.detect_anomaly(metric_name, value)
        
        if is_anomaly:
            self.log_audit(
                "anomaly_detected",
                "system",
                f"Anomaly in {metric_name}",
                {"metric": metric_name, "value": value},
                "warning"
            )
        
        return is_anomaly
    
    def check_blacklist(self, user_id: str) -> bool:
        """Check if user is blacklisted."""
        return user_id in self.blacklist
    
    def add_to_blacklist(self, user_id: str, reason: str):
        """Add user to blacklist."""
        self.blacklist.add(user_id)
        self.log_audit(
            "blacklist_add",
            "system",
            f"User blacklisted: {reason}",
            {"user_id": user_id, "reason": reason},
            "critical"
        )
        print(f"⚠️  User blacklisted: {user_id}")
    
    def remove_from_blacklist(self, user_id: str):
        """Remove user from blacklist."""
        self.blacklist.discard(user_id)
        self.log_audit(
            "blacklist_remove",
            "system",
            "User removed from blacklist",
            {"user_id": user_id},
            "info"
        )
    
    def log_audit(self, event_type: str, user_id: str, action: str, details: Dict, severity: str = "info"):
        """Log audit event."""
        log_entry = AuditLog(
            timestamp=time.time(),
            event_type=event_type,
            user_id=user_id,
            action=action,
            details=details,
            severity=severity
        )
        
        self.audit_log.append(log_entry)
        
        # Write to file
        try:
            with open(self.audit_file, 'a') as f:
                f.write(json.dumps({
                    "timestamp": log_entry.timestamp,
                    "event_type": log_entry.event_type,
                    "user_id": log_entry.user_id,
                    "action": log_entry.action,
                    "details": log_entry.details,
                    "severity": log_entry.severity
                }) + "\n")
        except Exception as e:
            print(f"⚠️  Error writing audit log: {e}")
    
    def check_emergency_override(self, override_code: str) -> bool:
        """
        Check emergency override code.
        
        This is a kill-switch for critical situations.
        """
        code_hash = hashlib.sha256(override_code.encode()).hexdigest()
        
        if code_hash == self.emergency_hash:
            self.log_audit(
                "emergency_override",
                "system",
                "Emergency override activated",
                {},
                "critical"
            )
            print("🚨 EMERGENCY OVERRIDE ACTIVATED!")
            return True
        
        return False
    
    def get_security_stats(self) -> Dict:
        """Get security statistics."""
        return {
            "blacklist_size": len(self.blacklist),
            "audit_log_size": len(self.audit_log),
            "anomaly_alerts": len(self.anomaly_detector.alerts),
            "rate_limit_configs": len(self.rate_limiter.configs)
        }


# Singleton
_manager: Optional[SecurityManager] = None


def get_security_manager() -> SecurityManager:
    """Get singleton security manager."""
    global _manager
    if _manager is None:
        _manager = SecurityManager()
    return _manager


if __name__ == "__main__":
    print("🛡️ Security Manager Test\n")
    
    manager = get_security_manager()
    
    # Test rate limiting
    print("1️⃣ Testing Rate Limiting...")
    for i in range(5):
        allowed, remaining = manager.check_rate_limit("user-1", "messaging")
        print(f"   Request {i+1}: {'✅ Allowed' if allowed else '❌ Blocked'} (Remaining: {remaining})")
    
    # Test anomaly detection
    print("\n2️⃣ Testing Anomaly Detection...")
    for i in range(20):
        value = 10.0 if i < 19 else 100.0  # Last value is anomalous
        is_anomaly = manager.detect_anomaly("test_metric", value)
        if is_anomaly:
            print(f"   ⚠️  Anomaly detected: {value}")
    
    # Test blacklist
    print("\n3️⃣ Testing Blacklist...")
    manager.add_to_blacklist("bad-user", "Spam detected")
    is_blacklisted = manager.check_blacklist("bad-user")
    print(f"   User blacklisted: {is_blacklisted}")
    
    # Test audit log
    print("\n4️⃣ Testing Audit Log...")
    manager.log_audit("test_event", "user-1", "Test action", {"test": "data"}, "info")
    print(f"   Audit log entries: {len(manager.audit_log)}")
    
    # Stats
    print("\n📊 Security Stats:")
    stats = manager.get_security_stats()
    for key, value in stats.items():
        print(f"   {key}: {value}")
    
    print("\n✅ Security Manager test complete!")
