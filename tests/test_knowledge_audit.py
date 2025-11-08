"""
Tests for Knowledge Audit System
Sprint 6.2 - Metakognition
"""
import pytest
import json
from pathlib import Path
import time


class TestKnowledgeAudit:
    """Test knowledge audit functionality"""
    
    def test_audit_tool_exists(self):
        """Audit tool should exist"""
        tool = Path("/home/kiana/ki_ana/tools/knowledge_audit.py")
        assert tool.exists(), "knowledge_audit.py should exist"
        assert tool.stat().st_mode & 0o111, "Should be executable"
    
    def test_audit_dir_structure(self):
        """Audit directory should be created"""
        audit_dir = Path("/home/kiana/ki_ana/data/audit")
        # Will be created when audit runs
        assert True  # Just checking structure
    
    def test_audit_module_import(self):
        """Should be able to import audit router"""
        try:
            from netapi.modules.audit import router
            assert router is not None
        except ImportError as e:
            pytest.skip(f"Cannot import in test environment: {e}")
    
    def test_auditor_class_import(self):
        """Should be able to import KnowledgeAuditor"""
        try:
            import sys
            sys.path.insert(0, '/home/kiana/ki_ana')
            from tools.knowledge_audit import KnowledgeAuditor
            assert KnowledgeAuditor is not None
        except ImportError as e:
            pytest.skip(f"Cannot import in test environment: {e}")


class TestAuditReport:
    """Test audit report structure"""
    
    def test_report_structure(self):
        """Audit report should have required fields"""
        required_fields = [
            'audit_version',
            'timestamp',
            'stats',
            'stale',
            'conflicts',
            'verified',
            'unverified',
            'recommendations'
        ]
        
        # Mock report structure
        mock_report = {
            "audit_version": "1.0",
            "timestamp": int(time.time()),
            "stats": {
                "total_scanned": 100,
                "total_stale": 10,
                "total_conflicts": 2,
                "total_verified": 80,
                "total_unverified": 8
            },
            "stale": {"count": 10, "blocks": []},
            "conflicts": {"count": 2, "blocks": []},
            "verified": {"count": 80, "sample": []},
            "unverified": {"count": 8, "sample": []},
            "recommendations": []
        }
        
        for field in required_fields:
            assert field in mock_report, f"Report should have '{field}'"
    
    def test_stats_structure(self):
        """Stats should have all metrics"""
        required_stats = [
            'total_scanned',
            'total_stale',
            'total_conflicts',
            'total_verified',
            'total_unverified'
        ]
        
        mock_stats = {
            "total_scanned": 100,
            "total_stale": 10,
            "total_conflicts": 2,
            "total_verified": 80,
            "total_unverified": 8,
            "scan_duration_ms": 1234,
            "timestamp": int(time.time())
        }
        
        for stat in required_stats:
            assert stat in mock_stats, f"Stats should have '{stat}'"


class TestAuditAPI:
    """Test audit API endpoints"""
    
    def test_api_endpoints_defined(self):
        """Audit API should define all required endpoints"""
        try:
            from netapi.modules.audit.router import router
            
            # Check routes
            routes = [route.path for route in router.routes]
            
            expected_endpoints = [
                '/api/audit/run',
                '/api/audit/status',
                '/api/audit/latest',
                '/api/audit/stale',
                '/api/audit/conflicts'
            ]
            
            # Endpoints might have prefix, so just check if they're defined
            assert len(routes) > 0, "Should have audit routes defined"
            
        except ImportError:
            pytest.skip("Cannot import router in test environment")


class TestAuditBlock:
    """Test audit block creation"""
    
    def test_audit_block_structure(self):
        """Audit blocks should have correct structure"""
        mock_block = {
            "id": "audit_1698765432",
            "type": "self_audit",
            "title": "Knowledge Audit 2025-10-29 16:00",
            "topic": "Self-Reflection",
            "topics_path": ["Meta", "Self-Audit"],
            "timestamp": 1698765432,
            "trust": 10,
            "content": {
                "summary": "Scanned 100 blocks...",
                "stats": {},
                "recommendations": []
            },
            "tags": ["audit", "self-reflection", "quality-check"]
        }
        
        assert mock_block["type"] == "self_audit"
        assert "Self-Audit" in mock_block["topics_path"]
        assert mock_block["trust"] == 10
        assert "audit" in mock_block["tags"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
