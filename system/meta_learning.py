"""
Meta-Learning System

The AI analyzes its own performance and optimizes its learning strategies.

Process:
1. Track Performance - What works, what doesn't?
2. Identify Patterns - Where do I succeed/fail?
3. Optimize Strategies - Adjust learning approach
4. Self-Improve - Apply insights to future learning
"""
from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from collections import Counter, defaultdict


@dataclass
class PerformanceMetric:
    """Tracks a specific performance metric."""
    metric_name: str
    value: float
    timestamp: float
    context: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric_name": self.metric_name,
            "value": self.value,
            "timestamp": self.timestamp,
            "context": self.context
        }


@dataclass
class LearningInsight:
    """Represents an insight about learning performance."""
    insight_type: str  # "success_pattern", "failure_pattern", "optimization"
    description: str
    evidence: List[str]
    confidence: float  # 0.0-1.0
    action_recommended: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "insight_type": self.insight_type,
            "description": self.description,
            "evidence": self.evidence,
            "confidence": self.confidence,
            "action_recommended": self.action_recommended
        }


class MetaLearner:
    """Analyzes own performance and optimizes learning strategies."""
    
    def __init__(self):
        self.base_dir = Path.home() / "ki_ana"
        self.runtime_dir = self.base_dir / "runtime"
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        
        self.metrics_file = self.runtime_dir / "performance_metrics.json"
        self.insights_file = self.runtime_dir / "learning_insights.json"
        
        self.metrics: List[PerformanceMetric] = []
        self.insights: List[LearningInsight] = []
        
        self._load_state()
    
    def _load_state(self) -> None:
        """Load metrics and insights from disk."""
        try:
            if self.metrics_file.exists():
                data = json.loads(self.metrics_file.read_text())
                # Simplified loading
                self.metrics = data  # type: ignore
            
            if self.insights_file.exists():
                data = json.loads(self.insights_file.read_text())
                self.insights = data  # type: ignore
        except Exception:
            pass
    
    def _save_state(self) -> None:
        """Save metrics and insights to disk."""
        try:
            metrics_data = [m.to_dict() if hasattr(m, 'to_dict') else m for m in self.metrics[-1000:]]
            self.metrics_file.write_text(json.dumps(metrics_data, indent=2))
            
            insights_data = [i.to_dict() if hasattr(i, 'to_dict') else i for i in self.insights[-100:]]
            self.insights_file.write_text(json.dumps(insights_data, indent=2))
        except Exception:
            pass
    
    def track_metric(
        self,
        metric_name: str,
        value: float,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Track a performance metric.
        
        Examples:
        - answer_quality: 0.0-1.0
        - user_satisfaction: 0.0-1.0
        - response_time: seconds
        - confidence_score: 0.0-1.0
        """
        metric = PerformanceMetric(
            metric_name=metric_name,
            value=value,
            timestamp=time.time(),
            context=context or {}
        )
        
        self.metrics.append(metric)
        self._save_state()
    
    def analyze_performance(self) -> Dict[str, Any]:
        """
        Analyze overall performance.
        
        Returns metrics, trends, and patterns.
        """
        if not self.metrics:
            return {
                "ok": False,
                "reason": "No metrics tracked yet"
            }
        
        # Group metrics by name
        by_name = defaultdict(list)
        for m in self.metrics:
            if isinstance(m, PerformanceMetric):
                by_name[m.metric_name].append(m.value)
            elif isinstance(m, dict):
                by_name[m.get("metric_name", "unknown")].append(m.get("value", 0))
        
        # Calculate statistics
        stats = {}
        for name, values in by_name.items():
            stats[name] = {
                "count": len(values),
                "avg": sum(values) / len(values) if values else 0,
                "min": min(values) if values else 0,
                "max": max(values) if values else 0,
                "recent_avg": sum(values[-10:]) / len(values[-10:]) if len(values) >= 10 else sum(values) / len(values) if values else 0
            }
        
        # Detect trends
        trends = {}
        for name, values in by_name.items():
            if len(values) >= 5:
                recent = values[-5:]
                earlier = values[-10:-5] if len(values) >= 10 else values[:-5]
                
                if earlier:
                    recent_avg = sum(recent) / len(recent)
                    earlier_avg = sum(earlier) / len(earlier)
                    
                    if recent_avg > earlier_avg * 1.1:
                        trends[name] = "improving"
                    elif recent_avg < earlier_avg * 0.9:
                        trends[name] = "declining"
                    else:
                        trends[name] = "stable"
        
        return {
            "ok": True,
            "total_metrics": len(self.metrics),
            "tracked_metrics": list(by_name.keys()),
            "statistics": stats,
            "trends": trends
        }
    
    def identify_patterns(self) -> List[LearningInsight]:
        """
        Identify patterns in performance data.
        
        Looks for:
        - Success patterns (what works well?)
        - Failure patterns (what doesn't work?)
        - Optimization opportunities
        """
        insights = []
        
        if len(self.metrics) < 10:
            return insights
        
        # Analyze by metric type
        by_name = defaultdict(list)
        for m in self.metrics:
            if isinstance(m, PerformanceMetric):
                by_name[m.metric_name].append(m)
            elif isinstance(m, dict):
                by_name[m.get("metric_name", "unknown")].append(m)
        
        # Pattern 1: High performance metrics
        for name, metrics in by_name.items():
            values = [m.value if isinstance(m, PerformanceMetric) else m.get("value", 0) for m in metrics]
            avg = sum(values) / len(values) if values else 0
            
            if avg >= 0.8:
                insight = LearningInsight(
                    insight_type="success_pattern",
                    description=f"Hohe Performance bei '{name}' (Ø {avg:.2f})",
                    evidence=[f"{len(values)} Messungen mit Durchschnitt {avg:.2f}"],
                    confidence=0.8,
                    action_recommended="Aktuelle Strategie beibehalten"
                )
                insights.append(insight)
        
        # Pattern 2: Low performance metrics
        for name, metrics in by_name.items():
            values = [m.value if isinstance(m, PerformanceMetric) else m.get("value", 0) for m in metrics]
            avg = sum(values) / len(values) if values else 0
            
            if avg < 0.5:
                insight = LearningInsight(
                    insight_type="failure_pattern",
                    description=f"Niedrige Performance bei '{name}' (Ø {avg:.2f})",
                    evidence=[f"{len(values)} Messungen mit Durchschnitt {avg:.2f}"],
                    confidence=0.8,
                    action_recommended=f"Strategie für '{name}' optimieren"
                )
                insights.append(insight)
        
        # Pattern 3: Improving trends
        for name, metrics in by_name.items():
            if len(metrics) >= 10:
                recent = [m.value if isinstance(m, PerformanceMetric) else m.get("value", 0) for m in metrics[-5:]]
                earlier = [m.value if isinstance(m, PerformanceMetric) else m.get("value", 0) for m in metrics[-10:-5]]
                
                recent_avg = sum(recent) / len(recent)
                earlier_avg = sum(earlier) / len(earlier)
                
                if recent_avg > earlier_avg * 1.2:
                    insight = LearningInsight(
                        insight_type="optimization",
                        description=f"Starke Verbesserung bei '{name}' (+{((recent_avg/earlier_avg - 1) * 100):.0f}%)",
                        evidence=[f"Von {earlier_avg:.2f} auf {recent_avg:.2f}"],
                        confidence=0.9,
                        action_recommended="Erfolgreiche Änderungen dokumentieren und replizieren"
                    )
                    insights.append(insight)
        
        self.insights = insights
        self._save_state()
        
        return insights
    
    def optimize_strategies(self) -> Dict[str, Any]:
        """
        Generate optimization recommendations based on patterns.
        
        Returns concrete actions to improve performance.
        """
        # First identify patterns
        insights = self.identify_patterns()
        
        if not insights:
            return {
                "ok": True,
                "message": "Nicht genug Daten für Optimierung",
                "recommendations": []
            }
        
        # Group by type
        by_type = defaultdict(list)
        for insight in insights:
            if isinstance(insight, LearningInsight):
                by_type[insight.insight_type].append(insight)
            elif isinstance(insight, dict):
                by_type[insight.get("insight_type", "unknown")].append(insight)
        
        # Generate recommendations
        recommendations = []
        
        # From success patterns
        for insight in by_type.get("success_pattern", []):
            if isinstance(insight, LearningInsight):
                desc = insight.description
                action = insight.action_recommended
            else:
                desc = insight.get("description", "")
                action = insight.get("action_recommended", "")
            
            recommendations.append({
                "priority": "high",
                "category": "preserve_success",
                "description": desc,
                "action": action
            })
        
        # From failure patterns
        for insight in by_type.get("failure_pattern", []):
            if isinstance(insight, LearningInsight):
                desc = insight.description
                action = insight.action_recommended
            else:
                desc = insight.get("description", "")
                action = insight.get("action_recommended", "")
            
            recommendations.append({
                "priority": "critical",
                "category": "fix_weakness",
                "description": desc,
                "action": action
            })
        
        # From optimizations
        for insight in by_type.get("optimization", []):
            if isinstance(insight, LearningInsight):
                desc = insight.description
                action = insight.action_recommended
            else:
                desc = insight.get("description", "")
                action = insight.get("action_recommended", "")
            
            recommendations.append({
                "priority": "medium",
                "category": "replicate_success",
                "description": desc,
                "action": action
            })
        
        # Sort by priority
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        recommendations.sort(key=lambda r: priority_order.get(r["priority"], 99))
        
        return {
            "ok": True,
            "insights_analyzed": len(insights),
            "recommendations": recommendations,
            "summary": self._generate_summary(recommendations)
        }
    
    def _generate_summary(self, recommendations: List[Dict[str, Any]]) -> str:
        """Generate human-readable summary of recommendations."""
        if not recommendations:
            return "Keine Optimierungen erforderlich - Performance ist stabil."
        
        critical = sum(1 for r in recommendations if r["priority"] == "critical")
        high = sum(1 for r in recommendations if r["priority"] == "high")
        
        summary = f"Analyse ergab {len(recommendations)} Empfehlungen: "
        
        if critical > 0:
            summary += f"{critical} kritisch, "
        if high > 0:
            summary += f"{high} wichtig, "
        
        summary += f"{len(recommendations) - critical - high} weitere."
        
        return summary
    
    def get_stats(self) -> Dict[str, Any]:
        """Get meta-learning statistics."""
        analysis = self.analyze_performance()
        
        return {
            "metrics_tracked": len(self.metrics),
            "insights_generated": len(self.insights),
            "performance_analysis": analysis,
            "last_optimization": self.insights[-1].to_dict() if self.insights and isinstance(self.insights[-1], LearningInsight) else None
        }


# Global instance
_meta_learner = MetaLearner()


def get_meta_learner() -> MetaLearner:
    """Get global meta-learner instance."""
    return _meta_learner
