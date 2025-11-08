"""
System Predictor

Predicts issues before they happen.
"""

from typing import Dict, Any, List
from loguru import logger
from datetime import datetime, timedelta


class SystemPredictor:
    """
    Predictive System Intelligence
    
    Predicts:
    - Disk space running out
    - Performance degradation
    - Potential failures
    - Maintenance needs
    """
    
    def __init__(self):
        self.history: List[Dict] = []
        self.predictions: List[Dict] = []
        
    def analyze_trends(self, current_state: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Analyze trends and predict issues
        
        Args:
            current_state: Current system state
            
        Returns:
            List of predictions
        """
        self.history.append({
            "timestamp": datetime.now().isoformat(),
            "state": current_state
        })
        
        # Keep only last 100 states
        if len(self.history) > 100:
            self.history = self.history[-100:]
        
        predictions = []
        
        # Predict disk space
        disk_pred = self._predict_disk_space()
        if disk_pred:
            predictions.append(disk_pred)
        
        # Predict memory issues
        mem_pred = self._predict_memory_issues()
        if mem_pred:
            predictions.append(mem_pred)
        
        # Predict performance degradation
        perf_pred = self._predict_performance_issues()
        if perf_pred:
            predictions.append(perf_pred)
        
        self.predictions = predictions
        return predictions
    
    def _predict_disk_space(self) -> Dict[str, Any]:
        """Predict when disk will be full"""
        if len(self.history) < 10:
            return None
        
        # Get disk usage trend
        recent = self.history[-10:]
        disk_values = []
        
        for state in recent:
            if "disk" in state["state"]:
                for partition in state["state"]["disk"].get("partitions", []):
                    if partition.get("mountpoint") == "/":
                        disk_values.append(partition.get("usage_percent", 0))
        
        if len(disk_values) < 5:
            return None
        
        # Simple linear regression
        avg_increase = (disk_values[-1] - disk_values[0]) / len(disk_values)
        
        if avg_increase > 0.5:  # Growing more than 0.5% per measurement
            days_until_full = (100 - disk_values[-1]) / avg_increase
            
            if days_until_full < 30:
                return {
                    "type": "disk_space",
                    "severity": "high" if days_until_full < 7 else "medium",
                    "message": f"Disk space will be full in ~{int(days_until_full)} days",
                    "recommendation": "Clean up old files or add more storage"
                }
        
        return None
    
    def _predict_memory_issues(self) -> Dict[str, Any]:
        """Predict memory issues"""
        if len(self.history) < 5:
            return None
        
        recent = self.history[-5:]
        mem_values = [s["state"].get("memory", {}).get("percent", 0) for s in recent]
        
        avg_mem = sum(mem_values) / len(mem_values)
        
        if avg_mem > 85:
            return {
                "type": "memory",
                "severity": "high",
                "message": "High memory usage detected consistently",
                "recommendation": "Consider closing unused applications or adding more RAM"
            }
        
        return None
    
    def _predict_performance_issues(self) -> Dict[str, Any]:
        """Predict performance degradation"""
        if len(self.history) < 10:
            return None
        
        recent = self.history[-10:]
        cpu_values = [s["state"].get("cpu", {}).get("percent", 0) for s in recent]
        
        avg_cpu = sum(cpu_values) / len(cpu_values)
        
        if avg_cpu > 70:
            return {
                "type": "performance",
                "severity": "medium",
                "message": "System performance may degrade with high CPU usage",
                "recommendation": "Consider optimizing or upgrading system"
            }
        
        return None
    
    def get_active_predictions(self) -> List[Dict[str, Any]]:
        """Get current predictions"""
        return self.predictions
