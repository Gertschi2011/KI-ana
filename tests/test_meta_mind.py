"""
Unit tests for Meta-Mind
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from netapi.core.meta_mind import (
    MetaMind,
    SystemState,
    ImprovementPlan,
    HealthStatus,
    CapabilityGap
)


class TestMetaMind:
    """Test suite for MetaMind"""
    
    @pytest.fixture
    def meta(self):
        """Create MetaMind instance"""
        return MetaMind()
    
    def test_meta_mind_initialization(self, meta):
        """Test that meta-mind initializes correctly"""
        assert len(meta._state_history) == 0
        assert meta.thresholds is not None
        assert "cpu_warning" in meta.thresholds
    
    def test_evaluate_system_state(self, meta):
        """Test system state evaluation"""
        state = meta.evaluate_system_state()
        
        assert isinstance(state, SystemState)
        assert state.cpu_percent >= 0
        assert state.memory_percent >= 0
        assert state.health_status in list(HealthStatus)
    
    def test_health_assessment(self, meta):
        """Test health assessment logic"""
        # Test excellent health
        status, warnings = meta._assess_health(
            cpu=20.0,
            memory=30.0,
            quality=0.9,
            retry_rate=0.1,
            response_time=1000,
            tool_success=0.95
        )
        
        assert status == HealthStatus.EXCELLENT
        assert len(warnings) == 0
        
        # Test critical health
        status, warnings = meta._assess_health(
            cpu=98.0,  # Critical!
            memory=95.0,  # Critical!
            quality=0.3,  # Critical!
            retry_rate=0.6,  # Critical!
            response_time=15000,  # Critical!
            tool_success=0.3
        )
        
        assert status == HealthStatus.CRITICAL
        assert len(warnings) > 0
    
    def test_plan_improvements_high_retry(self, meta):
        """Test improvement planning for high retry rate"""
        # Simulate state with high retry rate
        state = SystemState(
            timestamp=0,
            cpu_percent=30.0,
            memory_percent=40.0,
            memory_available_mb=2000,
            avg_response_time_ms=2000,
            avg_quality_score=0.7,
            retry_rate=0.4,  # High!
            total_interactions=100,
            tool_success_rate=0.8,
            health_status=HealthStatus.DEGRADED
        )
        
        meta._state_history.append(state)
        
        plans = meta.plan_improvements()
        
        # Should suggest improvement for retry rate
        assert len(plans) > 0
        retry_plans = [p for p in plans if p.gap == CapabilityGap.HIGH_RETRY_RATE]
        assert len(retry_plans) > 0
    
    def test_plan_improvements_low_quality(self, meta):
        """Test improvement planning for low quality"""
        state = SystemState(
            timestamp=0,
            cpu_percent=30.0,
            memory_percent=40.0,
            memory_available_mb=2000,
            avg_response_time_ms=2000,
            avg_quality_score=0.5,  # Low!
            retry_rate=0.2,
            total_interactions=100,
            tool_success_rate=0.8,
            health_status=HealthStatus.DEGRADED
        )
        
        meta._state_history.append(state)
        
        plans = meta.plan_improvements()
        
        quality_plans = [p for p in plans if p.gap == CapabilityGap.LOW_QUALITY_RESPONSES]
        assert len(quality_plans) > 0
    
    def test_plan_improvements_slow_performance(self, meta):
        """Test improvement planning for slow performance"""
        state = SystemState(
            timestamp=0,
            cpu_percent=30.0,
            memory_percent=40.0,
            memory_available_mb=2000,
            avg_response_time_ms=8000,  # Slow!
            avg_quality_score=0.8,
            retry_rate=0.2,
            total_interactions=100,
            tool_success_rate=0.8,
            health_status=HealthStatus.DEGRADED
        )
        
        meta._state_history.append(state)
        
        plans = meta.plan_improvements()
        
        perf_plans = [p for p in plans if p.gap == CapabilityGap.SLOW_PERFORMANCE]
        assert len(perf_plans) > 0
        # Should be able to autofix (caching)
        assert any(p.can_autofix for p in perf_plans)
    
    def test_trend_analysis(self, meta):
        """Test trend analysis over time"""
        # Add historical states with improving quality
        for i in range(10):
            quality = 0.5 + (i * 0.04)  # 0.5 -> 0.86
            state = SystemState(
                timestamp=i,
                cpu_percent=30.0,
                memory_percent=40.0,
                memory_available_mb=2000,
                avg_response_time_ms=2000,
                avg_quality_score=quality,
                retry_rate=0.2,
                total_interactions=i+1,
                tool_success_rate=0.8,
                health_status=HealthStatus.GOOD
            )
            meta._state_history.append(state)
        
        trends = meta.get_trends(["avg_quality_score"])
        
        assert "avg_quality_score" in trends
        assert trends["avg_quality_score"] == "improving"
    
    def test_trend_analysis_degrading(self, meta):
        """Test detection of degrading trends"""
        # Add states with degrading quality
        for i in range(10):
            quality = 0.9 - (i * 0.05)  # 0.9 -> 0.45
            state = SystemState(
                timestamp=i,
                cpu_percent=30.0,
                memory_percent=40.0,
                memory_available_mb=2000,
                avg_response_time_ms=2000,
                avg_quality_score=quality,
                retry_rate=0.2,
                total_interactions=i+1,
                tool_success_rate=0.8,
                health_status=HealthStatus.GOOD
            )
            meta._state_history.append(state)
        
        trends = meta.get_trends(["avg_quality_score"])
        
        assert trends["avg_quality_score"] == "degrading"
    
    def test_statistics(self, meta):
        """Test statistics generation"""
        # Add some states
        for i in range(3):
            state = SystemState(
                timestamp=i,
                cpu_percent=30.0,
                memory_percent=40.0,
                memory_available_mb=2000,
                avg_response_time_ms=2000,
                avg_quality_score=0.8,
                retry_rate=0.2,
                total_interactions=i+1,
                tool_success_rate=0.8,
                health_status=HealthStatus.GOOD,
                warnings=[]
            )
            meta._state_history.append(state)
        
        stats = meta.get_statistics()
        
        assert stats["states_tracked"] == 3
        assert stats["current_health"] == "good"
        assert "trends" in stats


class TestSystemState:
    """Test SystemState dataclass"""
    
    def test_state_creation(self):
        """Test creating system state"""
        state = SystemState(
            timestamp=123456,
            cpu_percent=45.0,
            memory_percent=60.0,
            memory_available_mb=2048,
            avg_response_time_ms=1500,
            avg_quality_score=0.85,
            retry_rate=0.15,
            total_interactions=100,
            tool_success_rate=0.9,
            health_status=HealthStatus.GOOD
        )
        
        assert state.cpu_percent == 45.0
        assert state.health_status == HealthStatus.GOOD
    
    def test_state_to_dict(self):
        """Test serialization to dict"""
        state = SystemState(
            timestamp=0,
            cpu_percent=45.0,
            memory_percent=60.0,
            memory_available_mb=2048,
            avg_response_time_ms=1500,
            avg_quality_score=0.85,
            retry_rate=0.15,
            total_interactions=100,
            tool_success_rate=0.9,
            health_status=HealthStatus.GOOD,
            warnings=["Test warning"]
        )
        
        d = state.to_dict()
        
        assert "resources" in d
        assert "performance" in d
        assert "health" in d
        assert d["health"]["status"] == "good"
        assert len(d["health"]["warnings"]) == 1


class TestImprovementPlan:
    """Test ImprovementPlan dataclass"""
    
    def test_plan_creation(self):
        """Test creating improvement plan"""
        plan = ImprovementPlan(
            priority=1,
            gap=CapabilityGap.LOW_QUALITY_RESPONSES,
            description="Quality too low",
            action="Improve prompts",
            estimated_impact="Quality +20%",
            can_autofix=False
        )
        
        assert plan.priority == 1
        assert plan.gap == CapabilityGap.LOW_QUALITY_RESPONSES
        assert not plan.can_autofix
    
    def test_plan_to_dict(self):
        """Test serialization"""
        plan = ImprovementPlan(
            priority=2,
            gap=CapabilityGap.SLOW_PERFORMANCE,
            description="Slow",
            action="Enable caching",
            estimated_impact="30% faster",
            can_autofix=True
        )
        
        d = plan.to_dict()
        
        assert d["priority"] == 2
        assert d["gap"] == "slow_performance"
        assert d["can_autofix"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
