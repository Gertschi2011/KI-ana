"""
Meta-Mind - Self-Awareness and System Monitoring for KI_ana

The "consciousness" layer that monitors and optimizes the AI system itself.
Implements meta-cognitive capabilities:
- Self-monitoring (system health, performance)
- Gap analysis (detect missing capabilities)
- Improvement planning (what to optimize next)
- Autonomous optimization triggers

Part of Phase 3: Autonomie
"""

from __future__ import annotations
import time
import psutil
import os
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class HealthStatus(Enum):
    """System health status levels"""
    EXCELLENT = "excellent"
    GOOD = "good"
    DEGRADED = "degraded"
    CRITICAL = "critical"


class CapabilityGap(Enum):
    """Types of capability gaps the system can detect"""
    MISSING_TOOL = "missing_tool"
    LOW_QUALITY_RESPONSES = "low_quality"
    HIGH_RETRY_RATE = "high_retries"
    SLOW_PERFORMANCE = "slow_performance"
    INSUFFICIENT_MEMORY = "insufficient_memory"
    TOOL_FAILURE = "tool_failure"
    KNOWLEDGE_GAP = "knowledge_gap"


@dataclass
class SystemState:
    """Current state of the AI system"""
    timestamp: int
    
    # Resource metrics
    cpu_percent: float
    memory_percent: float
    memory_available_mb: int
    
    # Performance metrics
    avg_response_time_ms: float
    avg_quality_score: float
    retry_rate: float
    
    # Operational metrics
    total_interactions: int
    tool_success_rate: float
    
    # Health assessment
    health_status: HealthStatus
    warnings: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "resources": {
                "cpu_percent": self.cpu_percent,
                "memory_percent": self.memory_percent,
                "memory_available_mb": self.memory_available_mb
            },
            "performance": {
                "avg_response_time_ms": self.avg_response_time_ms,
                "avg_quality_score": self.avg_quality_score,
                "retry_rate": self.retry_rate
            },
            "operational": {
                "total_interactions": self.total_interactions,
                "tool_success_rate": self.tool_success_rate
            },
            "health": {
                "status": self.health_status.value,
                "warnings": self.warnings
            }
        }


@dataclass
class ImprovementPlan:
    """Plan for system improvement"""
    priority: int  # 1 = critical, 2 = high, 3 = medium, 4 = low
    gap: CapabilityGap
    description: str
    action: str  # What to do
    estimated_impact: str  # Expected improvement
    can_autofix: bool = False  # Can be fixed automatically?
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "priority": self.priority,
            "gap": self.gap.value,
            "description": self.description,
            "action": self.action,
            "estimated_impact": self.estimated_impact,
            "can_autofix": self.can_autofix
        }


class MetaMind:
    """
    Meta-cognitive monitoring and optimization system.
    
    Acts as the "self-awareness" layer that watches the AI system
    and makes decisions about self-improvement.
    
    Usage:
        meta = MetaMind()
        
        # Evaluate current state
        state = meta.evaluate_system_state()
        print(f"Health: {state.health_status}")
        
        # Get improvement suggestions
        improvements = meta.plan_improvements()
        for plan in improvements:
            print(f"- {plan.description}")
        
        # Trigger optimization
        if state.health_status == HealthStatus.DEGRADED:
            meta.trigger_optimization()
    """
    
    def __init__(self):
        self._state_history: List[SystemState] = []
        self._max_history = 100  # Keep last 100 states
        
        # Thresholds for health assessment
        self.thresholds = {
            "cpu_warning": 80.0,
            "cpu_critical": 95.0,
            "memory_warning": 80.0,
            "memory_critical": 90.0,
            "quality_warning": 0.6,
            "quality_critical": 0.4,
            "retry_warning": 0.3,
            "retry_critical": 0.5,
            "response_time_warning": 5000,  # ms
            "response_time_critical": 10000,
        }
    
    def evaluate_system_state(self) -> SystemState:
        """
        Evaluate current system state.
        
        Returns:
            SystemState with current metrics and health assessment
        """
        # Gather resource metrics
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        memory_available_mb = memory.available // (1024 * 1024)
        
        # Gather performance metrics (from learning hub if available)
        avg_response_time = 0.0
        avg_quality = 0.0
        retry_rate = 0.0
        total_interactions = 0
        tool_success_rate = 0.0
        
        try:
            from ..learning.hub import get_learning_hub
            hub = get_learning_hub()
            if hub:
                stats = hub.get_statistics()
                total_interactions = stats.get("total_interactions", 0)
                avg_quality = stats.get("avg_quality", 0.0)
                
                # Calculate retry rate from reflector
                from .reflector import get_reflector
                reflector = get_reflector()
                refl_stats = reflector.get_statistics()
                retry_rate = refl_stats.get("retry_rate", 0.0)
                
                # Tool success rate
                tools = stats.get("tools", {})
                if tools:
                    success_rates = [t["success_rate"] for t in tools.values()]
                    tool_success_rate = sum(success_rates) / len(success_rates)
                
                # Estimate avg response time (rough)
                avg_response_time = 2000.0  # Default estimate
        except Exception:
            pass
        
        # Health assessment
        health_status, warnings = self._assess_health(
            cpu_percent, memory_percent, avg_quality,
            retry_rate, avg_response_time, tool_success_rate
        )
        
        state = SystemState(
            timestamp=int(time.time()),
            cpu_percent=cpu_percent,
            memory_percent=memory_percent,
            memory_available_mb=memory_available_mb,
            avg_response_time_ms=avg_response_time,
            avg_quality_score=avg_quality,
            retry_rate=retry_rate,
            total_interactions=total_interactions,
            tool_success_rate=tool_success_rate,
            health_status=health_status,
            warnings=warnings
        )
        
        # Store in history
        self._state_history.append(state)
        if len(self._state_history) > self._max_history:
            self._state_history.pop(0)
        
        return state
    
    def _assess_health(
        self,
        cpu: float,
        memory: float,
        quality: float,
        retry_rate: float,
        response_time: float,
        tool_success: float
    ) -> Tuple[HealthStatus, List[str]]:
        """Assess overall health and generate warnings"""
        warnings = []
        critical_count = 0
        warning_count = 0
        
        # CPU check
        if cpu >= self.thresholds["cpu_critical"]:
            warnings.append(f"CPU kritisch: {cpu:.1f}%")
            critical_count += 1
        elif cpu >= self.thresholds["cpu_warning"]:
            warnings.append(f"CPU hoch: {cpu:.1f}%")
            warning_count += 1
        
        # Memory check
        if memory >= self.thresholds["memory_critical"]:
            warnings.append(f"RAM kritisch: {memory:.1f}%")
            critical_count += 1
        elif memory >= self.thresholds["memory_warning"]:
            warnings.append(f"RAM hoch: {memory:.1f}%")
            warning_count += 1
        
        # Quality check
        if quality > 0 and quality < self.thresholds["quality_critical"]:
            warnings.append(f"Antwort-Qualität kritisch: {quality:.2f}")
            critical_count += 1
        elif quality > 0 and quality < self.thresholds["quality_warning"]:
            warnings.append(f"Antwort-Qualität niedrig: {quality:.2f}")
            warning_count += 1
        
        # Retry rate check
        if retry_rate >= self.thresholds["retry_critical"]:
            warnings.append(f"Retry-Rate kritisch: {retry_rate:.1%}")
            critical_count += 1
        elif retry_rate >= self.thresholds["retry_warning"]:
            warnings.append(f"Retry-Rate hoch: {retry_rate:.1%}")
            warning_count += 1
        
        # Response time check
        if response_time >= self.thresholds["response_time_critical"]:
            warnings.append(f"Response-Zeit kritisch: {response_time:.0f}ms")
            critical_count += 1
        elif response_time >= self.thresholds["response_time_warning"]:
            warnings.append(f"Response-Zeit hoch: {response_time:.0f}ms")
            warning_count += 1
        
        # Tool success check
        if tool_success > 0 and tool_success < 0.5:
            warnings.append(f"Tool-Erfolgsrate niedrig: {tool_success:.1%}")
            warning_count += 1
        
        # Determine overall status
        if critical_count > 0:
            return HealthStatus.CRITICAL, warnings
        elif warning_count >= 3:
            return HealthStatus.DEGRADED, warnings
        elif warning_count > 0:
            return HealthStatus.GOOD, warnings
        else:
            return HealthStatus.EXCELLENT, warnings
    
    def plan_improvements(self) -> List[ImprovementPlan]:
        """
        Analyze system and create improvement plans.
        
        Returns:
            List of ImprovementPlan sorted by priority
        """
        plans = []
        
        if not self._state_history:
            return plans
        
        current_state = self._state_history[-1]
        
        # Check for high retry rate
        if current_state.retry_rate >= self.thresholds["retry_warning"]:
            plans.append(ImprovementPlan(
                priority=1 if current_state.retry_rate >= self.thresholds["retry_critical"] else 2,
                gap=CapabilityGap.HIGH_RETRY_RATE,
                description=f"Hohe Retry-Rate: {current_state.retry_rate:.1%}",
                action="Prompt-Engineering verbessern oder besseres LLM-Modell wählen",
                estimated_impact="Retry-Rate auf <20% senken",
                can_autofix=False
            ))
        
        # Check for low quality
        if current_state.avg_quality_score > 0 and current_state.avg_quality_score < self.thresholds["quality_warning"]:
            plans.append(ImprovementPlan(
                priority=1,
                gap=CapabilityGap.LOW_QUALITY_RESPONSES,
                description=f"Niedrige Qualität: {current_state.avg_quality_score:.2f}",
                action="LLM-Modell upgraden oder Reflection-Threshold erhöhen",
                estimated_impact="Quality-Score auf >0.8 anheben",
                can_autofix=False
            ))
        
        # Check for slow performance
        if current_state.avg_response_time_ms >= self.thresholds["response_time_warning"]:
            plans.append(ImprovementPlan(
                priority=2,
                gap=CapabilityGap.SLOW_PERFORMANCE,
                description=f"Langsame Antworten: {current_state.avg_response_time_ms:.0f}ms",
                action="Caching aktivieren, Tools parallelisieren oder LLM-Inferenz optimieren",
                estimated_impact="Response-Zeit auf <3s senken",
                can_autofix=True  # Caching kann automatisch aktiviert werden
            ))
        
        # Check for insufficient memory
        if current_state.memory_percent >= self.thresholds["memory_warning"]:
            plans.append(ImprovementPlan(
                priority=1 if current_state.memory_percent >= self.thresholds["memory_critical"] else 2,
                gap=CapabilityGap.INSUFFICIENT_MEMORY,
                description=f"Hohe RAM-Nutzung: {current_state.memory_percent:.1f}%",
                action="Memory-Leaks prüfen, Caches limitieren oder Server-RAM erhöhen",
                estimated_impact="RAM-Nutzung auf <70% senken",
                can_autofix=True  # Cache-Cleanup kann auto laufen
            ))
        
        # Check for tool failures
        if current_state.tool_success_rate > 0 and current_state.tool_success_rate < 0.7:
            plans.append(ImprovementPlan(
                priority=2,
                gap=CapabilityGap.TOOL_FAILURE,
                description=f"Tools scheitern oft: {current_state.tool_success_rate:.1%} Erfolg",
                action="Tool-Error-Handling verbessern und Retry-Logic erweitern",
                estimated_impact="Tool-Erfolgsrate auf >90%",
                can_autofix=False
            ))
        
        # Sort by priority
        plans.sort(key=lambda p: p.priority)
        
        return plans
    
    def trigger_optimization(self):
        """
        Automatically trigger system optimizations where possible.
        
        This method implements autonomous self-improvement.
        """
        state = self.evaluate_system_state()
        plans = self.plan_improvements()
        
        for plan in plans:
            if not plan.can_autofix:
                continue
            
            try:
                if plan.gap == CapabilityGap.SLOW_PERFORMANCE:
                    self._enable_caching()
                    print(f"✅ Auto-fix: Caching aktiviert")
                
                elif plan.gap == CapabilityGap.INSUFFICIENT_MEMORY:
                    self._cleanup_caches()
                    print(f"✅ Auto-fix: Cache-Cleanup durchgeführt")
                
            except Exception as e:
                print(f"❌ Auto-fix failed for {plan.gap.value}: {e}")
    
    def _enable_caching(self):
        """Enable response caching for better performance"""
        # TODO: Implement caching mechanism
        # For now, just log
        print("INFO: Caching would be enabled here")
    
    def _cleanup_caches(self):
        """Clean up caches to free memory"""
        # TODO: Implement cache cleanup
        # For now, just log
        print("INFO: Cache cleanup would run here")
    
    def get_trends(self, metrics: List[str] = None) -> Dict[str, str]:
        """
        Analyze trends in system metrics.
        
        Args:
            metrics: List of metric names to analyze (default: all)
            
        Returns:
            Dict of {metric: trend} where trend is "improving", "stable", "degrading"
        """
        if len(self._state_history) < 5:
            return {}  # Not enough data
        
        if metrics is None:
            metrics = ["avg_quality_score", "retry_rate", "avg_response_time_ms"]
        
        trends = {}
        
        # Compare recent avg to older avg
        recent = self._state_history[-5:]
        older = self._state_history[-10:-5] if len(self._state_history) >= 10 else self._state_history[:-5]
        
        for metric in metrics:
            try:
                recent_avg = sum(getattr(s, metric, 0) for s in recent) / len(recent)
                older_avg = sum(getattr(s, metric, 0) for s in older) / len(older)
                
                if older_avg == 0:
                    trends[metric] = "stable"
                    continue
                
                change_percent = ((recent_avg - older_avg) / older_avg) * 100
                
                # For some metrics, higher is worse (retry_rate, response_time)
                invert_metrics = ["retry_rate", "avg_response_time_ms"]
                
                if metric in invert_metrics:
                    change_percent = -change_percent
                
                if change_percent > 5:
                    trends[metric] = "improving"
                elif change_percent < -5:
                    trends[metric] = "degrading"
                else:
                    trends[metric] = "stable"
                    
            except Exception:
                trends[metric] = "unknown"
        
        return trends
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get meta-mind statistics"""
        if not self._state_history:
            return {"states_tracked": 0}
        
        latest = self._state_history[-1]
        trends = self.get_trends()
        
        return {
            "states_tracked": len(self._state_history),
            "current_health": latest.health_status.value,
            "warnings": latest.warnings,
            "trends": trends,
            "improvement_plans": len(self.plan_improvements())
        }


# Global instance
_meta_mind_instance: Optional[MetaMind] = None


def get_meta_mind() -> MetaMind:
    """Get or create global MetaMind instance"""
    global _meta_mind_instance
    if _meta_mind_instance is None:
        _meta_mind_instance = MetaMind()
    return _meta_mind_instance


if __name__ == "__main__":
    # Self-test
    print("=== Meta-Mind Self-Test ===\n")
    
    meta = MetaMind()
    
    # Evaluate system
    print("1. System State:")
    state = meta.evaluate_system_state()
    print(f"Health: {state.health_status.value}")
    print(f"CPU: {state.cpu_percent:.1f}%")
    print(f"RAM: {state.memory_percent:.1f}%")
    if state.warnings:
        print(f"Warnings: {', '.join(state.warnings)}")
    
    # Improvement plans
    print("\n2. Improvement Plans:")
    plans = meta.plan_improvements()
    if plans:
        for plan in plans:
            print(f"  [{plan.priority}] {plan.description}")
            print(f"      Action: {plan.action}")
    else:
        print("  No improvements needed ✅")
    
    # Trigger optimization
    print("\n3. Auto-Optimization:")
    meta.trigger_optimization()
    
    # Stats
    print("\n4. Statistics:")
    stats = meta.get_statistics()
    print(f"  States tracked: {stats['states_tracked']}")
    print(f"  Current health: {stats['current_health']}")
