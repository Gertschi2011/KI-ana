"""
Telemetry System für KI_ana (Opt-in, Privacy-First)

Features:
- Opt-in only (disabled by default)
- Anonymous metrics only
- No personal data
- Local aggregation
- User control
"""
from __future__ import annotations
import time
import json
from pathlib import Path
from typing import Dict, Optional, List
from dataclasses import dataclass, asdict
import sys

# Add system path
sys.path.insert(0, str(Path.home() / "ki_ana" / "system"))


@dataclass
class TelemetryMetric:
    """Anonymous telemetry metric."""
    metric_name: str
    value: float
    timestamp: float
    tags: Dict[str, str]
    
    def to_dict(self) -> Dict:
        return asdict(self)


class TelemetryService:
    """
    Privacy-First Telemetry Service.
    
    - Opt-in only (disabled by default)
    - Anonymous metrics only
    - No personal data collected
    - User has full control
    """
    
    _instance: Optional['TelemetryService'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        
        self._initialized = True
        
        # Check opt-in status
        self.enabled = self._check_opt_in()
        
        # Metrics storage
        self.metrics: List[TelemetryMetric] = []
        
        # Local storage
        self.telemetry_dir = Path.home() / "ki_ana" / "data" / "telemetry"
        self.telemetry_dir.mkdir(parents=True, exist_ok=True)
        
        self.metrics_file = self.telemetry_dir / "metrics.jsonl"
        
        if self.enabled:
            print(f"✅ Telemetry enabled (opt-in)")
        else:
            print(f"ℹ️  Telemetry disabled (opt-in required)")
    
    def _check_opt_in(self) -> bool:
        """Check if user has opted in to telemetry."""
        opt_in_file = Path.home() / "ki_ana" / ".telemetry_opt_in"
        return opt_in_file.exists()
    
    def opt_in(self):
        """Enable telemetry (user consent)."""
        opt_in_file = Path.home() / "ki_ana" / ".telemetry_opt_in"
        opt_in_file.write_text(json.dumps({
            "opted_in": True,
            "timestamp": time.time(),
            "version": "3.0.0"
        }))
        self.enabled = True
        print("✅ Telemetry enabled")
        print("   Only anonymous metrics will be collected")
        print("   No personal data is collected")
    
    def opt_out(self):
        """Disable telemetry."""
        opt_in_file = Path.home() / "ki_ana" / ".telemetry_opt_in"
        if opt_in_file.exists():
            opt_in_file.unlink()
        self.enabled = False
        print("✅ Telemetry disabled")
    
    def record_metric(self, metric_name: str, value: float, tags: Dict[str, str] = None):
        """
        Record anonymous metric.
        
        Only if user has opted in!
        """
        if not self.enabled:
            return
        
        metric = TelemetryMetric(
            metric_name=metric_name,
            value=value,
            timestamp=time.time(),
            tags=tags or {}
        )
        
        self.metrics.append(metric)
        
        # Save to file
        self._save_metric(metric)
    
    def _save_metric(self, metric: TelemetryMetric):
        """Save metric to local file."""
        try:
            with open(self.metrics_file, 'a') as f:
                f.write(json.dumps(metric.to_dict()) + '\n')
        except Exception as e:
            print(f"⚠️  Error saving metric: {e}")
    
    def get_aggregated_metrics(self) -> Dict:
        """
        Get aggregated anonymous metrics.
        
        Returns only aggregated data, no individual events.
        """
        if not self.enabled:
            return {"enabled": False}
        
        # Load all metrics
        metrics_by_name = {}
        
        try:
            if self.metrics_file.exists():
                with open(self.metrics_file, 'r') as f:
                    for line in f:
                        metric_data = json.loads(line.strip())
                        name = metric_data['metric_name']
                        
                        if name not in metrics_by_name:
                            metrics_by_name[name] = []
                        
                        metrics_by_name[name].append(metric_data['value'])
        except Exception as e:
            print(f"⚠️  Error loading metrics: {e}")
        
        # Aggregate
        aggregated = {}
        for name, values in metrics_by_name.items():
            aggregated[name] = {
                "count": len(values),
                "avg": sum(values) / len(values) if values else 0,
                "min": min(values) if values else 0,
                "max": max(values) if values else 0
            }
        
        return {
            "enabled": True,
            "metrics": aggregated,
            "total_events": sum(len(v) for v in metrics_by_name.values())
        }
    
    def get_privacy_report(self) -> Dict:
        """Get privacy report showing what data is collected."""
        return {
            "telemetry_enabled": self.enabled,
            "data_collected": [
                "Average latency (ms)",
                "Error rate (%)",
                "Peer count",
                "Block sync time (ms)"
            ] if self.enabled else [],
            "data_NOT_collected": [
                "Personal information",
                "IP addresses",
                "Device identifiers",
                "Message content",
                "User data",
                "Location data"
            ],
            "storage": "Local only (not sent to servers)",
            "control": "User can opt-out anytime"
        }


# Singleton
_service: Optional[TelemetryService] = None


def get_telemetry_service() -> TelemetryService:
    """Get singleton telemetry service."""
    global _service
    if _service is None:
        _service = TelemetryService()
    return _service


# Convenience functions
def record_latency(operation: str, latency_ms: float):
    """Record operation latency."""
    service = get_telemetry_service()
    service.record_metric("latency", latency_ms, {"operation": operation})


def record_error(error_type: str):
    """Record error occurrence."""
    service = get_telemetry_service()
    service.record_metric("error", 1.0, {"type": error_type})


def record_peer_count(count: int):
    """Record peer count."""
    service = get_telemetry_service()
    service.record_metric("peer_count", float(count), {})


if __name__ == "__main__":
    print("📊 Telemetry Service Test\n")
    
    service = get_telemetry_service()
    
    # Show privacy report
    print("🔒 Privacy Report:")
    report = service.get_privacy_report()
    print(f"   Enabled: {report['telemetry_enabled']}")
    print(f"   Data collected: {len(report['data_collected'])} metrics")
    print(f"   Data NOT collected: {len(report['data_NOT_collected'])} items")
    print(f"   Storage: {report['storage']}")
    
    # Test opt-in
    print("\n📝 Testing opt-in...")
    service.opt_in()
    
    # Record some metrics
    print("\n📊 Recording test metrics...")
    record_latency("embedding", 245.0)
    record_latency("vector_search", 126.0)
    record_peer_count(3)
    
    # Get aggregated metrics
    print("\n📈 Aggregated Metrics:")
    metrics = service.get_aggregated_metrics()
    if metrics.get("enabled"):
        print(f"   Total events: {metrics['total_events']}")
        for name, stats in metrics.get("metrics", {}).items():
            print(f"   {name}: avg={stats['avg']:.1f}, count={stats['count']}")
    
    # Test opt-out
    print("\n🚫 Testing opt-out...")
    service.opt_out()
    
    print("\n✅ Telemetry Service test complete!")
